"""g5_promotion. Deterministic registry-promotion tools.

Deterministic core for the G5 — Registry Promotion spec.
The dev -> staging -> production -> archived state machine,
signature validation, min-metric gating, and audit-trail
helpers live here.  The MLflow Model Registry adapter is
referenced in the spec but MLflow is an optional dependency;
the adapter is loaded lazily and a no-op fallback runs when
mlflow is unavailable.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


STAGES: List[str] = ["dev", "staging", "production", "archived"]

# Forward-only transitions allowed (dev -> staging -> production,
# and from any non-archived to archived). demote is an explicit
# request type and accepts production -> staging, staging -> dev,
# or any -> archived.
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "dev": ["staging", "archived"],
    "staging": ["production", "dev", "archived"],
    "production": ["staging", "archived"],
    "archived": [],
}


def _now() -> float:
    return time.time()


def _auto_uuid() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class ModelVersionRecord:
    """A registry entry.  Mutable; the promotion helpers update
    ``stage`` and ``audit_trail`` in place."""

    model_id: str
    version: str
    stage: str = "dev"
    input_schema: Optional[List[str]] = None
    output_type: str = "scalar"
    metrics: Dict[str, float] = field(default_factory=dict)
    is_champion: bool = False
    created_at: float = field(default_factory=_now)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "stage": self.stage,
            "input_schema": list(self.input_schema) if self.input_schema else None,
            "output_type": self.output_type,
            "metrics": dict(self.metrics),
            "is_champion": self.is_champion,
            "created_at": self.created_at,
            "audit_trail": list(self.audit_trail),
        }


def register_version(
    model_id: str,
    version: str,
    *,
    input_schema: Optional[Sequence[str]] = None,
    output_type: str = "scalar",
    metrics: Optional[Dict[str, float]] = None,
    registry: Optional[Dict[str, ModelVersionRecord]] = None,
) -> Tuple[Dict[str, ModelVersionRecord], ModelVersionRecord]:
    """Add a new version to the in-memory registry.

    Mutates the supplied ``registry`` dict in place (creating a new
    one only when ``registry is None``) so callers can hold a
    stable reference across multiple registrations.
    """
    if registry is None:
        reg: Dict[str, ModelVersionRecord] = {}
    else:
        reg = registry
    record = ModelVersionRecord(
        model_id=model_id,
        version=version,
        stage="dev",
        input_schema=list(input_schema) if input_schema else None,
        output_type=output_type,
        metrics=dict(metrics or {}),
        is_champion=False,
        created_at=_now(),
    )
    reg[version] = record
    return reg, record


def validate_signature(
    candidate: ModelVersionRecord,
    target: ModelVersionRecord,
) -> Tuple[bool, List[str]]:
    """Check that two records share the same input schema and
    output type.  Returns (ok, issues)."""
    issues: List[str] = []
    if candidate.input_schema and target.input_schema:
        if list(candidate.input_schema) != list(target.input_schema):
            issues.append(
                f"input_schema mismatch: {candidate.input_schema} "
                f"vs {target.input_schema}"
            )
    if candidate.output_type != target.output_type:
        issues.append(
            f"output_type mismatch: {candidate.output_type!r} "
            f"vs {target.output_type!r}"
        )
    return (not issues), issues


def evaluate_min_metrics(
    metrics: Mapping[str, float],
    required: Mapping[str, float],
) -> Tuple[bool, List[str]]:
    """All required metric thresholds must be met (or exceeded)."""
    issues: List[str] = []
    for name, threshold in required.items():
        actual = metrics.get(name)
        if actual is None:
            issues.append(f"missing metric: {name}")
            continue
        if actual < threshold:
            issues.append(
                f"metric {name!r} {actual:.4f} < required {threshold:.4f}"
            )
    return (not issues), issues


def request_promotion(
    record: ModelVersionRecord,
    to_stage: str,
    *,
    reason: str,
    actor: str = "system",
    require_approval: bool = True,
    min_metrics: Optional[Mapping[str, float]] = None,
    target_for_signature: Optional[ModelVersionRecord] = None,
) -> Dict[str, Any]:
    """Submit a promotion request.

    Returns a dict with status (one of "approved", "pending_approval",
    "rejected"), an audit_trail entry, and any validation issues.
    When ``require_approval`` is True and the transition is
    dev->staging or staging->production, status is pending_approval.
    """
    if to_stage not in STAGES:
        return {
            "status": "rejected",
            "to_stage": to_stage,
            "issues": [f"unknown target stage: {to_stage!r}"],
            "audit_trail_entry": None,
        }
    if to_stage not in VALID_TRANSITIONS[record.stage]:
        return {
            "status": "rejected",
            "to_stage": to_stage,
            "issues": [
                f"illegal transition: {record.stage} -> {to_stage}"
            ],
            "audit_trail_entry": None,
        }

    issues: List[str] = []
    if target_for_signature is not None:
        ok, sig_issues = validate_signature(record, target_for_signature)
        issues.extend(sig_issues)
    if min_metrics:
        ok_m, m_issues = evaluate_min_metrics(record.metrics, min_metrics)
        issues.extend(m_issues)

    needs_approval = require_approval and to_stage in {
        "staging",
        "production",
    }
    if issues:
        status = "rejected"
    elif needs_approval:
        status = "pending_approval"
    else:
        status = "approved"

    entry = {
        "event": "promotion_request",
        "actor": actor,
        "reason": reason,
        "from_stage": record.stage,
        "to_stage": to_stage,
        "status": status,
        "issues": issues,
        "at": _now(),
    }
    record.audit_trail.append(entry)
    return {
        "status": status,
        "to_stage": to_stage,
        "issues": issues,
        "audit_trail_entry": entry,
    }


def approve(
    record: ModelVersionRecord,
    to_stage: str,
    *,
    actor: str = "governance",
    reason: str = "approved",
    auto_archive_previous: bool = True,
    registry: Optional[Dict[str, ModelVersionRecord]] = None,
) -> Dict[str, Any]:
    """Approve a pending promotion.  Updates the record's stage
    and (optionally) auto-archives the previous production
    version.  Returns the new state plus an audit entry."""
    prev_stage = record.stage
    record.stage = to_stage
    archived: List[str] = []
    if (
        auto_archive_previous
        and to_stage == "production"
        and registry is not None
    ):
        for v, rec in registry.items():
            if rec is record:
                continue
            if v == record.version:
                continue
            if rec.stage == "production":
                rec.stage = "archived"
                rec.audit_trail.append(
                    {
                        "event": "auto_archive",
                        "actor": actor,
                        "reason": f"replaced by {record.version}",
                        "at": _now(),
                    }
                )
                archived.append(v)
    # Mark this version as champion when it lands in production.
    if to_stage == "production" and registry is not None:
        for rec in registry.values():
            if rec is record:
                rec.is_champion = True
            else:
                rec.is_champion = False
    entry = {
        "event": "promotion_approved",
        "actor": actor,
        "reason": reason,
        "from_stage": prev_stage,
        "to_stage": to_stage,
        "at": _now(),
    }
    record.audit_trail.append(entry)
    return {
        "status": "approved",
        "to_stage": to_stage,
        "archived": archived,
        "is_champion": record.is_champion,
        "audit_trail_entry": entry,
    }


def demote(
    record: ModelVersionRecord,
    to_stage: str,
    *,
    actor: str = "ml_engineer",
    reason: str = "",
    registry: Optional[Dict[str, ModelVersionRecord]] = None,
) -> Dict[str, Any]:
    if to_stage not in VALID_TRANSITIONS[record.stage]:
        return {
            "status": "rejected",
            "issues": [
                f"illegal transition: {record.stage} -> {to_stage}"
            ],
            "audit_trail_entry": None,
        }
    return approve(
        record,
        to_stage,
        actor=actor,
        reason=reason or f"demote {record.stage}->{to_stage}",
        auto_archive_previous=False,
        registry=registry,
    )


def get_version_by_stage(
    registry: Mapping[str, ModelVersionRecord],
    stage: str,
) -> Optional[str]:
    """Pick the highest version (lexicographic / max) record in
    the requested stage.  Returns the version key or None."""
    in_stage = [v for v, r in registry.items() if r.stage == stage]
    if not in_stage:
        return None
    # Sort by integer (or fallback to string) so v10 > v9.
    def _key(v: str) -> Tuple[int, str]:
        try:
            return (int(v), v)
        except ValueError:
            return (-1, v)

    return max(in_stage, key=_key)


def mlflow_alias_sync(
    model_id: str,
    version: str,
    alias: str,
    registry_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """Best-effort MLflow alias update.  Returns an in-memory ack
    if mlflow is unavailable; the platform layer can call this
    to keep the registry and MLflow aliases in sync."""
    try:
        import mlflow  # type: ignore
        from mlflow.tracking import MlflowClient  # type: ignore
    except Exception:  # pragma: no cover
        return {
            "status": "no_mlflow",
            "model_id": model_id,
            "version": version,
            "alias": alias,
        }
    if registry_uri:
        mlflow.set_registry_uri(registry_uri)
    client = MlflowClient()
    client.set_registered_model_alias(
        name=model_id, alias=alias, version=version
    )
    return {
        "status": "ok",
        "model_id": model_id,
        "version": version,
        "alias": alias,
    }


__all__ = [
    "STAGES",
    "VALID_TRANSITIONS",
    "ModelVersionRecord",
    "register_version",
    "validate_signature",
    "evaluate_min_metrics",
    "request_promotion",
    "approve",
    "demote",
    "get_version_by_stage",
    "mlflow_alias_sync",
]
