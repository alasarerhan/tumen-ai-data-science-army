"""
k2_modelops
===========

Deterministic tools supporting **K2 — ModelOps Kontrol Merkezi**
(spec ``docs/specs/K2-modelops-center.md``).

The actual MLflow + HITL registry lives in
``apps/platform-api-app/platform_api/services/modelops_service.py``
and ``model_registry``. This module provides the *view* layer that
the ModelOps UI consumes:

* Champion-pinning decisions (mirrors F2's recommendation flag).
* Registry summary aggregation across stages.
* Detail-page metadata bundle (drift, perf, lineage links).
* Retrain-policy + champion-challenger surface hooks.

Public surface
--------------

* :func:`aggregate_registry_summary` — roll up the model-registry
  table into per-stage counts + drift rollup.
* :func:`build_model_detail` — produce the Model Detail page bundle:
  registry card, perf snapshot, drift rollup, lineage links.
* :func:`record_champion_change` — emit an audit-friendly dict when
  the champion changes (consumed by F2's promote flow).
* :func:`K2_MODELOPS_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Common stages + state taxonomy
# ---------------------------------------------------------------------------


STAGES: List[str] = ["staging", "production", "archived"]


@dataclass
class RegistryEntrySummary:
    model_id: str
    version: str
    stage: str
    is_champion: bool
    drift_status: str = "ok"
    last_metric: Optional[float] = None
    promoted_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "stage": self.stage,
            "is_champion": self.is_champion,
            "drift_status": self.drift_status,
            "last_metric": self.last_metric,
            "promoted_at": self.promoted_at,
        }


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------


def aggregate_registry_summary(
    entries: Sequence[Mapping[str, Any]],
    drift_statuses: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Aggregate the registry into a summary card for the K2 home page.

    Parameters
    ----------
    entries : sequence of mapping
        Each entry must have ``model_id``, ``version``, ``stage``,
        optionally ``is_champion``, ``last_metric``, ``promoted_at``.
    drift_statuses : optional mapping
        ``model_id → drift_status`` ("ok" | "warning" | "critical").

    Returns
    -------
    dict with keys ``stage_counts`` (``{stage: count}``),
    ``champion`` (single dict or None), ``drift_rollup``
    (``{status: count}``), ``entries`` (per-entry summaries).
    """
    drift_statuses = dict(drift_statuses or {})
    stage_counts: Dict[str, int] = {s: 0 for s in STAGES}
    drift_rollup: Dict[str, int] = {"ok": 0, "warning": 0, "critical": 0}
    champion: Optional[Dict[str, Any]] = None
    per_entry: List[Dict[str, Any]] = []

    for e in entries:
        if not isinstance(e, Mapping):
            continue
        mid = str(e.get("model_id", ""))
        ver = str(e.get("version", ""))
        stage = str(e.get("stage", "staging"))
        is_champ = bool(e.get("is_champion", False))
        drift = drift_statuses.get(mid, "ok")
        if stage in stage_counts:
            stage_counts[stage] += 1
        if drift in drift_rollup:
            drift_rollup[drift] += 1
        summary = RegistryEntrySummary(
            model_id=mid,
            version=ver,
            stage=stage,
            is_champion=is_champ,
            drift_status=drift,
            last_metric=e.get("last_metric"),
            promoted_at=e.get("promoted_at"),
        )
        per_entry.append(summary.to_dict())
        if is_champ and champion is None:
            champion = summary.to_dict()

    return {
        "stage_counts": stage_counts,
        "champion": champion,
        "drift_rollup": drift_rollup,
        "entries": per_entry,
        "n_models": len(per_entry),
        "n_champions": sum(1 for e in per_entry if e.get("is_champion")),
    }


# ---------------------------------------------------------------------------
# Model Detail bundle
# ---------------------------------------------------------------------------


@dataclass
class ModelDetailBundle:
    summary: Dict[str, Any]
    perf_snapshot: Optional[Dict[str, Any]]
    drift_snapshot: Optional[Dict[str, Any]]
    lineage_links: List[str] = field(default_factory=list)
    retrain_policy_id: Optional[str] = None
    champion_challenger_comparison_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "perf_snapshot": self.perf_snapshot,
            "drift_snapshot": self.drift_snapshot,
            "lineage_links": list(self.lineage_links),
            "retrain_policy_id": self.retrain_policy_id,
            "champion_challenger_comparison_id": self.champion_challenger_comparison_id,
        }


def build_model_detail(
    entry: Mapping[str, Any],
    *,
    perf_snapshot: Optional[Mapping[str, Any]] = None,
    drift_snapshot: Optional[Mapping[str, Any]] = None,
    lineage_links: Optional[Sequence[str]] = None,
    retrain_policy_id: Optional[str] = None,
    champion_challenger_comparison_id: Optional[str] = None,
) -> ModelDetailBundle:
    """Build the Model Detail bundle for the K2 detail tabs.

    Fields:
    * summary — registry entry summary.
    * perf_snapshot — F1 evaluation output (or None).
    * drift_snapshot — G1 drift result (or None).
    * lineage_links — J12 lineage pointers.
    * retrain_policy_id — pointer to G2 policy if any.
    * champion_challenger_comparison_id — pointer to F2 comparison.
    """
    if not isinstance(entry, Mapping):
        raise ValueError("entry must be a mapping")
    summary = RegistryEntrySummary(
        model_id=str(entry.get("model_id", "")),
        version=str(entry.get("version", "")),
        stage=str(entry.get("stage", "staging")),
        is_champion=bool(entry.get("is_champion", False)),
        drift_status=str(entry.get("drift_status", "ok")),
        last_metric=entry.get("last_metric"),
        promoted_at=entry.get("promoted_at"),
    ).to_dict()
    return ModelDetailBundle(
        summary=summary,
        perf_snapshot=dict(perf_snapshot) if perf_snapshot else None,
        drift_snapshot=dict(drift_snapshot) if drift_snapshot else None,
        lineage_links=list(lineage_links or []),
        retrain_policy_id=retrain_policy_id,
        champion_challenger_comparison_id=champion_challenger_comparison_id,
    )


# ---------------------------------------------------------------------------
# Champion-change audit
# ---------------------------------------------------------------------------


def record_champion_change(
    model_id: str,
    previous_version: Optional[str],
    new_version: str,
    *,
    decided_by: str = "f2.promote",
    decided_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an audit-trail entry for a champion swap.

    Consumed by the F2 → K2 promote flow. ``decided_at`` defaults to
    ``None`` (caller decides whether to stamp it now or let the audit
    middleware handle the timestamp).
    """
    return {
        "model_id": model_id,
        "previous_version": previous_version,
        "new_version": new_version,
        "decided_by": decided_by,
        "decided_at": decided_at,
    }


__all__ = [
    "STAGES",
    "RegistryEntrySummary",
    "aggregate_registry_summary",
    "build_model_detail",
    "record_champion_change",
    "K2_MODELOPS_TOOL_NAMES",
]


K2_MODELOPS_TOOL_NAMES = [
    "k2_aggregate_registry",
    "k2_model_detail",
    "k2_record_champion_change",
]
