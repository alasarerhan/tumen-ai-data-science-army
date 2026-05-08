"""FinOps endpoints for cost optimization and resource management.

Provides endpoints for:
- Artifact cleanup
- Cache management
- Cost metrics
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_tenant_admin
from platform_api.core.config import settings
from platform_api.db.session import get_db
from platform_api.services.artifact_cleanup_service import (
    cleanup_expired_artifacts,
    cleanup_old_artifacts,
    list_expired_artifacts,
)

router = APIRouter(prefix="/v1/finops", tags=["finops"])


class CleanupRequest(BaseModel):
    dry_run: bool = True
    older_than_days: int | None = None


class CleanupResponse(BaseModel):
    dry_run: bool
    artifacts_deleted: int
    files_deleted: int
    bytes_freed: int
    errors: list[str] = []


class CacheStatsResponse(BaseModel):
    backend: str
    entries: int
    max_entries: int | None = None
    key_prefix: str | None = None


class FinOpsConfigResponse(BaseModel):
    artifact_retention_days: int
    audit_log_retention_days: int
    log_retention_days: int
    chat_upload_max_mb: int
    agent_cache_enabled: bool
    agent_cache_ttl_seconds: int
    openai_cache_enabled: bool
    webhook_max_retries: int
    webhook_backoff_max_seconds: float
    malware_scan_mode: str
    egress_strict_mode: bool
    artifact_redirect_strict_mode: bool


@router.post("/artifacts/cleanup", response_model=CleanupResponse)
async def run_artifact_cleanup(
    body: CleanupRequest,
    context: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Run artifact cleanup (admin only).

    FinOps: Deletes expired or old artifacts to reduce storage costs.
    """
    if body.older_than_days:
        stats = cleanup_old_artifacts(
            db,
            tenant_id=context["tenant_id"],
            older_than_days=body.older_than_days,
            dry_run=body.dry_run,
        )
    else:
        stats = cleanup_expired_artifacts(
            db,
            tenant_id=context["tenant_id"],
            dry_run=body.dry_run,
        )

    return stats


@router.get("/artifacts/expired")
async def list_expired(
    context: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List expired artifacts (admin only)."""
    expired = list_expired_artifacts(db, tenant_id=context["tenant_id"])
    return {
        "count": len(expired),
        "artifacts": [
            {
                "id": str(a.id),
                "kind": a.kind,
                "uri": a.uri,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
            }
            for a in expired[:100]
        ],
    }


@router.get("/cache/stats", response_model=CacheStatsResponse)
async def get_cache_stats(
    context: dict = Depends(require_tenant_admin),
) -> dict:
    """Get agent cache statistics (admin only)."""
    from ai_data_science_team.utils.agent_cache import get_agent_cache

    cache = get_agent_cache()
    return cache.stats()


@router.post("/cache/clear")
async def clear_cache(
    context: dict = Depends(require_tenant_admin),
) -> dict:
    """Clear agent cache (admin only)."""
    from ai_data_science_team.utils.agent_cache import get_agent_cache

    cache = get_agent_cache()
    cache.clear()
    return {"status": "cleared"}


@router.get("/config", response_model=FinOpsConfigResponse)
async def get_finops_config(
    context: dict = Depends(require_tenant_admin),
) -> dict:
    """Get FinOps configuration (admin only)."""
    return {
        "artifact_retention_days": settings.artifact_retention_days,
        "audit_log_retention_days": settings.audit_log_retention_days,
        "log_retention_days": settings.log_retention_days,
        "chat_upload_max_mb": settings.chat_upload_max_mb,
        "agent_cache_enabled": settings.agent_cache_enabled,
        "agent_cache_ttl_seconds": settings.agent_cache_ttl_seconds,
        "openai_cache_enabled": settings.openai_cache_enabled,
        "webhook_max_retries": settings.webhook_max_retries,
        "webhook_backoff_max_seconds": settings.webhook_backoff_max_seconds,
        "malware_scan_mode": settings.malware_scan_mode,
        "egress_strict_mode": settings.egress_strict_mode,
        "artifact_redirect_strict_mode": settings.artifact_redirect_strict_mode,
    }


@router.get("/summary")
async def get_finops_summary(
    context: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get FinOps cost optimization summary (admin only)."""
    from ai_data_science_team.utils.agent_cache import get_agent_cache
    from platform_api.db.models import Artifact, ChatUpload, WorkflowRun

    cache = get_agent_cache()
    cache_stats = cache.stats()

    tenant_id = context["tenant_id"]

    artifact_count = db.execute(
        select(func.count()).select_from(Artifact).where(Artifact.tenant_id == tenant_id)
    ).scalar() or 0

    upload_count = db.execute(
        select(func.count()).select_from(ChatUpload).where(ChatUpload.tenant_id == tenant_id)
    ).scalar() or 0

    run_count = db.execute(
        select(func.count()).select_from(WorkflowRun).where(WorkflowRun.tenant_id == tenant_id)
    ).scalar() or 0

    expired_count = len(list_expired_artifacts(db, tenant_id=tenant_id))

    return {
        "storage": {
            "artifacts": artifact_count,
            "uploads": upload_count,
            "expired_artifacts": expired_count,
        },
        "compute": {
            "workflow_runs": run_count,
        },
        "cache": cache_stats,
        "config": {
            "artifact_retention_days": settings.artifact_retention_days,
            "upload_max_mb": settings.chat_upload_max_mb,
            "agent_cache_enabled": settings.agent_cache_enabled,
        },
        "recommendations": _generate_recommendations(
            artifact_count, expired_count, cache_stats
        ),
    }


def _generate_recommendations(
    artifact_count: int,
    expired_count: int,
    cache_stats: dict,
) -> list[str]:
    recs = []

    if expired_count > 100:
        recs.append(
            f"Run artifact cleanup to free storage ({expired_count} expired artifacts)"
        )

    if artifact_count > 10000:
        recs.append(
            "Consider reducing artifact_retention_days to control storage growth"
        )

    if cache_stats.get("backend") == "memory":
        recs.append(
            "Configure Redis for agent_cache_redis_url to enable distributed caching"
        )

    if not recs:
        recs.append("FinOps configuration looks optimal")

    return recs
