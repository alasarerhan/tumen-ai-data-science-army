from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.db.models import Artifact, WorkflowRun

logger = logging.getLogger(__name__)

_strategy_cache: dict[str, tuple[list[str] | None, float]] = {}
_strategy_cache_lock = threading.Lock()
_CACHE_MAX_ENTRIES = 500


def _gather_workspace_stats(db, tenant_uuid, workspace_uuid):
    runs = list(
        db.execute(
            select(WorkflowRun).where(
                WorkflowRun.tenant_id == tenant_uuid,
                WorkflowRun.workspace_id == workspace_uuid,
            )
        ).scalars()
    )
    artifacts = list(
        db.execute(
            select(Artifact).where(
                Artifact.tenant_id == tenant_uuid,
                Artifact.workspace_id == workspace_uuid,
            )
        ).scalars()
    )
    return runs, artifacts


def _rule_based_recommendations(summary: dict) -> list[str]:
    run_count = summary["run_count"]
    artifact_count = summary["artifact_count"]
    status_dist = summary["run_status_distribution"]
    recs: list[str] = []
    failed = status_dist.get("FAILED", 0)
    completed = status_dist.get("COMPLETED", 0) + status_dist.get("Completed", 0)
    if failed > 0:
        failure_rate = failed / max(run_count, 1)
        if failure_rate > 0.5:
            recs.append(
                "Failure rate exceeds 50%; break workflow steps into smaller units and add "
                "retry logic with exponential back-off on each step."
            )
        else:
            recs.append(
                "Some runs are failing; define automatic alert rules and retry policies to "
                "improve operational reliability."
            )
    if completed == 0 and run_count > 0:
        recs.append(
            "No run has completed; review resource limits, timeout values, and "
            "dependent service availability."
        )
    if run_count == 0:
        recs.append(
            "No workflows executed yet; define a weekly automatic schedule to "
            "start the data rhythm and build baseline metrics."
        )
    if artifact_count < max(1, run_count // 2):
        recs.append(
            "Artifact production per run is low; ensure each workflow produces at least one "
            "report artifact to improve decision traceability."
        )
    if not recs:
        recs.append(
            "Flow appears healthy; periodically review quota and queue settings to "
            "optimize resource consumption."
        )
    return recs


def _cache_key(summary: dict) -> str:
    summary_for_hash = {k: v for k, v in summary.items() if k != "run_id"}
    return hashlib.sha256(json.dumps(summary_for_hash, sort_keys=True).encode()).hexdigest()[:16]


def _get_cached_recommendations(key: str) -> list[str] | None:
    from platform_api.core.config import settings

    if not settings.openai_cache_enabled:
        return None
    with _strategy_cache_lock:
        cached = _strategy_cache.get(key)
        if cached:
            if time.time() - cached[1] < settings.openai_cache_ttl_seconds:
                logger.debug("Strategy cache HIT: %s", key)
                return cached[0]
            else:
                _strategy_cache.pop(key, None)
    return None


def _set_cached_recommendations(key: str, recs: list[str] | None) -> None:
    from platform_api.core.config import settings

    if not settings.openai_cache_enabled:
        return
    with _strategy_cache_lock:
        if len(_strategy_cache) >= _CACHE_MAX_ENTRIES:
            oldest = min(_strategy_cache.items(), key=lambda x: x[1][1])
            _strategy_cache.pop(oldest[0], None)
        _strategy_cache[key] = (recs, time.time())
    logger.debug("Strategy cache SET: %s", key)


async def _openai_recommendations(summary: dict) -> list[str] | None:
    from platform_api.core.config import settings

    if not settings.openai_api_key:
        return None

    cache_key = _cache_key(summary)
    cached = _get_cached_recommendations(cache_key)
    if cached is not None:
        return cached

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        user_prompt = (
            "Below are the operational statistics of a data science platform workspace.\n"
            "Generate 3-5 practical, measurable, prioritized recommendations.\n"
            "Each recommendation: max 2 sentences, respond in Turkish.\n\n"
            f"Total workflow runs: {summary['run_count']}\n"
            f"Total artifacts: {summary['artifact_count']}\n"
            f"Run status distribution: {summary['run_status_distribution']}\n"
            f"Artifact type distribution: {summary['artifact_kind_distribution']}\n\n"
            "Output ONLY bullet points, one per line starting with '- '. No headings."
        )
        model = settings.openai_model_strategy or settings.openai_model
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI consultant for data science platforms. "
                        "Give concise, actionable recommendations. Always respond in Turkish."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=600,
        )
        raw = response.choices[0].message.content or ""
        lines = [ln.lstrip("•-– ").strip() for ln in raw.splitlines() if ln.strip()]
        recs = [ln for ln in lines if len(ln) > 15]
        if recs:
            _set_cached_recommendations(cache_key, recs)
            return recs
    except Exception as exc:
        logger.warning("OpenAI strategy report failed, falling back to rules: %s", exc)
    return None


async def generate_workspace_strategy_report(
    db: Session,
    *,
    tenant_id: str,
    workspace_id: str,
    run_id: str | None = None,
) -> dict:
    tenant_uuid = uuid.UUID(tenant_id)
    workspace_uuid = uuid.UUID(workspace_id)
    runs, artifacts = _gather_workspace_stats(db, tenant_uuid, workspace_uuid)
    run_status_counter = Counter(run.status for run in runs)
    artifact_kind_counter = Counter(artifact.kind for artifact in artifacts)
    summary: dict = {
        "run_count": len(runs),
        "artifact_count": len(artifacts),
        "run_status_distribution": dict(run_status_counter),
        "artifact_kind_distribution": dict(artifact_kind_counter),
        "run_id": run_id,  # echo back for caller convenience
    }
    recommendations = await _openai_recommendations(summary)
    powered_by = "openai"
    if not recommendations:
        recommendations = _rule_based_recommendations(summary)
        powered_by = "rules"
    return {
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "summary": summary,
        "recommendations": recommendations,
        "powered_by": powered_by,
    }
