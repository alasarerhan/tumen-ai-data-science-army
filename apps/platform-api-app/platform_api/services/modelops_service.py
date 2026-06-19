from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.db.models import Artifact, ModelDeploymentRecord, ModelMonitorSnapshot, ModelRegistryEntry
from platform_api.services.artifact_service import get_artifact_parent_ids

MODEL_KINDS = {"model", "model_binary", "model_package", "trained_model"}
METRIC_KINDS = {"metrics", "model_metrics", "evaluation", "model_evaluation", "evaluation_report", "drift_report"}


def get_modelops_summary(db: Session, *, workspace_id: uuid.UUID) -> dict[str, Any]:
    persisted_models = list(
        db.execute(
            select(ModelRegistryEntry)
            .where(ModelRegistryEntry.workspace_id == workspace_id)
            .order_by(ModelRegistryEntry.created_at.desc(), ModelRegistryEntry.id.desc())
        ).scalars()
    )
    persisted_monitors = list(
        db.execute(
            select(ModelMonitorSnapshot)
            .where(ModelMonitorSnapshot.workspace_id == workspace_id)
            .order_by(ModelMonitorSnapshot.created_at.desc(), ModelMonitorSnapshot.id.desc())
        ).scalars()
    )
    persisted_deployments = list(
        db.execute(
            select(ModelDeploymentRecord)
            .where(ModelDeploymentRecord.workspace_id == workspace_id)
            .order_by(ModelDeploymentRecord.created_at.desc(), ModelDeploymentRecord.id.desc())
        ).scalars()
    )

    artifacts = list(
        db.execute(
            select(Artifact)
            .where(Artifact.workspace_id == workspace_id)
            .where(Artifact.kind.in_(sorted(MODEL_KINDS | METRIC_KINDS)))
            .order_by(Artifact.created_at.desc())
        ).scalars()
    )
    model_artifacts = [item for item in artifacts if item.kind in MODEL_KINDS]
    metric_artifacts = [item for item in artifacts if item.kind in METRIC_KINDS]
    metrics_by_run = _group_by_run(metric_artifacts)
    artifact_registry = [_artifact_registry_entry(item, metrics_by_run.get(str(item.workflow_run_id), [])) for item in model_artifacts]
    artifact_monitors = [_artifact_monitor_entry(item) for item in metric_artifacts]
    monitors = [_persisted_monitor_entry(item) for item in persisted_monitors] + artifact_monitors
    deployments = [_deployment_entry(item) for item in persisted_deployments]
    deployment_by_model = _deployments_by_model(deployments)
    monitors_by_model = _monitors_by_model(monitors)
    if persisted_models:
        registry = [
            _persisted_registry_entry(item, monitors_by_model.get(str(item.id), []), deployment_by_model.get(str(item.id), []))
            for item in persisted_models
        ]
        artifact_fallback = artifact_registry
    else:
        registry = artifact_registry
        artifact_fallback = []
    retrain_candidates = [
        _retrain_candidate(entry, monitors)
        for entry in registry
        if _is_retrain_candidate(entry, monitors)
    ]
    return {
        "registry": registry,
        "monitors": monitors,
        "retrain_candidates": retrain_candidates,
        "metrics": {
            "registered_models": len(registry),
            "monitor_snapshots": len(monitors),
            "retrain_candidates": len(retrain_candidates),
            "deployments": len(deployments),
            "artifact_backed_candidates": len(artifact_fallback),
        },
        "status": {
            "registry": "persisted" if persisted_models else "artifact_backed",
            "monitoring": "persisted" if persisted_monitors else "artifact_backed",
            "deployment": "persisted" if persisted_deployments else "not_configured",
            "retraining": "candidate_detection",
        },
        "deployments": deployments,
        "artifact_backed_candidates": artifact_fallback[:20],
    }


def register_model(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    model_name: str,
    version: str,
    stage: str = "candidate",
    artifact_id: uuid.UUID | None = None,
    workflow_run_id: uuid.UUID | None = None,
    owner_user_id: uuid.UUID | None = None,
    approval_state: str = "not_reviewed",
    model_card: dict[str, Any] | None = None,
) -> ModelRegistryEntry:
    if artifact_id:
        _require_workspace_artifact(db, workspace_id=workspace_id, artifact_id=artifact_id)
    entry = ModelRegistryEntry(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        model_name=model_name.strip(),
        version=version.strip(),
        stage=stage,
        artifact_id=artifact_id,
        workflow_run_id=workflow_run_id,
        owner_user_id=owner_user_id,
        approval_state=approval_state,
        model_card_json=json.dumps(model_card or {}, default=str),
    )
    db.add(entry)
    db.flush()
    return entry


def record_monitor_snapshot(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    model_id: uuid.UUID,
    monitor_type: str,
    status: str,
    artifact_id: uuid.UUID | None = None,
    metric_name: str | None = None,
    metric_value: float | None = None,
    threshold_value: float | None = None,
    baseline: dict[str, Any] | None = None,
    owner_user_id: uuid.UUID | None = None,
    remediation_workflow: str | None = None,
) -> ModelMonitorSnapshot:
    _require_workspace_model(db, workspace_id=workspace_id, model_id=model_id)
    if artifact_id:
        _require_workspace_artifact(db, workspace_id=workspace_id, artifact_id=artifact_id)
    snapshot = ModelMonitorSnapshot(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        model_id=model_id,
        artifact_id=artifact_id,
        monitor_type=monitor_type,
        status=status,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold_value=threshold_value,
        baseline_json=json.dumps(baseline or {}, default=str),
        owner_user_id=owner_user_id,
        remediation_workflow=remediation_workflow,
    )
    db.add(snapshot)
    model = _require_workspace_model(db, workspace_id=workspace_id, model_id=model_id)
    model.monitoring_status = "linked"
    if monitor_type in {"drift", "data_drift", "concept_drift"}:
        model.drift_status = _worse_status(model.drift_status, status)
    if monitor_type in {"performance", "quality", "decay"}:
        model.performance_status = _worse_status(model.performance_status, status)
    db.flush()
    return snapshot


def record_deployment(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    model_id: uuid.UUID,
    environment: str,
    status: str,
    endpoint_url: str | None = None,
    deployed_at: datetime | None = None,
    rollback_model_id: uuid.UUID | None = None,
    rollback_notes: str | None = None,
    health_status: str = "unknown",
    last_health_check_at: datetime | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> ModelDeploymentRecord:
    model = _require_workspace_model(db, workspace_id=workspace_id, model_id=model_id)
    if rollback_model_id:
        _require_workspace_model(db, workspace_id=workspace_id, model_id=rollback_model_id)
    deployment = ModelDeploymentRecord(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        model_id=model_id,
        environment=environment,
        status=status,
        endpoint_url=_safe_endpoint_url(endpoint_url),
        deployed_at=deployed_at,
        rollback_model_id=rollback_model_id,
        rollback_notes=rollback_notes,
        health_status=health_status,
        last_health_check_at=last_health_check_at,
        created_by_user_id=created_by_user_id,
    )
    db.add(deployment)
    model.deployment_state = status
    db.flush()
    return deployment


def _group_by_run(artifacts: list[Artifact]) -> dict[str, list[Artifact]]:
    grouped: dict[str, list[Artifact]] = defaultdict(list)
    for item in artifacts:
        if item.workflow_run_id:
            grouped[str(item.workflow_run_id)].append(item)
    return grouped


def _artifact_registry_entry(model: Artifact, related_metrics: list[Artifact]) -> dict[str, Any]:
    return {
        "model_id": str(model.id),
        "model_name": model.produced_by_node_id or "artifact_model",
        "version": _version_label(model),
        "stage": "candidate",
        "artifact_id": str(model.id),
        "workflow_run_id": str(model.workflow_run_id) if model.workflow_run_id else None,
        "produced_by_node_id": model.produced_by_node_id,
        "parent_artifact_ids": get_artifact_parent_ids(model),
        "uri_scheme": _uri_scheme(model.uri),
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "approval_state": "not_reviewed",
        "deployment_state": "not_deployed",
        "monitoring_status": "linked" if related_metrics else "not_configured",
        "latest_metric_artifact_ids": [str(item.id) for item in related_metrics[:5]],
        "drift_status": _drift_status(related_metrics),
        "performance_status": _performance_status(related_metrics),
        "retrain_candidate": _drift_status(related_metrics) in {"warning", "critical"}
        or _performance_status(related_metrics) in {"warning", "critical"},
        "source": "artifact",
    }


def _persisted_registry_entry(
    model: ModelRegistryEntry,
    linked_monitors: list[dict[str, Any]],
    linked_deployments: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "model_id": str(model.id),
        "model_name": model.model_name,
        "version": model.version,
        "stage": model.stage,
        "artifact_id": str(model.artifact_id) if model.artifact_id else None,
        "workflow_run_id": str(model.workflow_run_id) if model.workflow_run_id else None,
        "produced_by_node_id": None,
        "parent_artifact_ids": [],
        "uri_scheme": "registry",
        "created_at": model.created_at.isoformat() if model.created_at else None,
        "approval_state": model.approval_state,
        "deployment_state": model.deployment_state,
        "monitoring_status": model.monitoring_status,
        "latest_metric_artifact_ids": [item["artifact_id"] for item in linked_monitors if item.get("artifact_id")][:5],
        "drift_status": _worst_status([model.drift_status, *[item.get("drift_status", "unknown") for item in linked_monitors]]),
        "performance_status": _worst_status(
            [model.performance_status, *[item.get("performance_status", "unknown") for item in linked_monitors]]
        ),
        "deployment_ids": [item["deployment_id"] for item in linked_deployments[:5]],
        "retrain_candidate": any(
            item.get("drift_status") in {"warning", "critical"} or item.get("performance_status") in {"warning", "critical"}
            for item in linked_monitors
        )
        or model.drift_status in {"warning", "critical"}
        or model.performance_status in {"warning", "critical"},
        "source": "registry",
    }


def _artifact_monitor_entry(artifact: Artifact) -> dict[str, Any]:
    metadata = _safe_json(getattr(artifact, "parent_artifact_ids_json", None))
    return {
        "monitor_id": str(artifact.id),
        "model_id": None,
        "artifact_id": str(artifact.id),
        "kind": artifact.kind,
        "monitor_type": artifact.kind,
        "workflow_run_id": str(artifact.workflow_run_id) if artifact.workflow_run_id else None,
        "produced_by_node_id": artifact.produced_by_node_id,
        "parent_artifact_ids": get_artifact_parent_ids(artifact),
        "uri_scheme": _uri_scheme(artifact.uri),
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        "freshness": "snapshot",
        "drift_status": _status_from_text(artifact, metadata, ["drift", "psi", "ks"]),
        "performance_status": _status_from_text(artifact, metadata, ["auc", "f1", "rmse", "mae", "accuracy", "decay"]),
        "alert_policy": "not_configured",
        "source": "artifact",
    }


def _persisted_monitor_entry(snapshot: ModelMonitorSnapshot) -> dict[str, Any]:
    drift_status = snapshot.status if snapshot.monitor_type in {"drift", "data_drift", "concept_drift"} else "unknown"
    performance_status = snapshot.status if snapshot.monitor_type in {"performance", "quality", "decay"} else "unknown"
    return {
        "monitor_id": str(snapshot.id),
        "model_id": str(snapshot.model_id),
        "artifact_id": str(snapshot.artifact_id) if snapshot.artifact_id else None,
        "kind": "model_monitor_snapshot",
        "monitor_type": snapshot.monitor_type,
        "workflow_run_id": None,
        "produced_by_node_id": None,
        "parent_artifact_ids": [str(snapshot.model_id)],
        "uri_scheme": "registry",
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "freshness": "snapshot",
        "drift_status": drift_status,
        "performance_status": performance_status,
        "status": snapshot.status,
        "metric_name": snapshot.metric_name,
        "metric_value": snapshot.metric_value,
        "threshold_value": snapshot.threshold_value,
        "alert_policy": "configured" if snapshot.threshold_value is not None else "not_configured",
        "source": "registry",
    }


def _deployment_entry(deployment: ModelDeploymentRecord) -> dict[str, Any]:
    return {
        "deployment_id": str(deployment.id),
        "model_id": str(deployment.model_id),
        "environment": deployment.environment,
        "status": deployment.status,
        "endpoint_configured": bool(deployment.endpoint_url),
        "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
        "rollback_model_id": str(deployment.rollback_model_id) if deployment.rollback_model_id else None,
        "rollback_configured": bool(deployment.rollback_model_id or deployment.rollback_notes),
        "health_status": deployment.health_status,
        "last_health_check_at": deployment.last_health_check_at.isoformat() if deployment.last_health_check_at else None,
        "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
    }


def _retrain_candidate(entry: dict[str, Any], monitors: list[dict[str, Any]]) -> dict[str, Any]:
    linked_monitor_ids = [
        monitor["monitor_id"]
        for monitor in monitors
        if entry["model_id"] in monitor.get("parent_artifact_ids", [])
        or monitor.get("workflow_run_id") == entry.get("workflow_run_id")
    ]
    return {
        "model_id": entry["model_id"],
        "version": entry["version"],
        "reason": "drift_or_performance_signal",
        "drift_status": entry["drift_status"],
        "performance_status": entry["performance_status"],
        "linked_monitor_ids": linked_monitor_ids[:5],
        "suggested_workflow": "retrain_from_latest_data",
        "action_state": "plan_required",
    }


def _is_retrain_candidate(entry: dict[str, Any], monitors: list[dict[str, Any]]) -> bool:
    if entry.get("retrain_candidate"):
        return True
    model_id = entry["model_id"]
    for monitor in monitors:
        if model_id in monitor.get("parent_artifact_ids", []):
            if monitor.get("drift_status") in {"warning", "critical"}:
                return True
            if monitor.get("performance_status") in {"warning", "critical"}:
                return True
    return False


def _monitors_by_model(monitors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for monitor in monitors:
        model_id = monitor.get("model_id")
        if model_id:
            grouped[model_id].append(monitor)
    return grouped


def _deployments_by_model(deployments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for deployment in deployments:
        grouped[deployment["model_id"]].append(deployment)
    return grouped


def _drift_status(metrics: list[Artifact]) -> str:
    statuses = [_status_from_text(item, _safe_json(getattr(item, "parent_artifact_ids_json", None)), ["drift", "psi", "ks"]) for item in metrics]
    return _worst_status(statuses)


def _performance_status(metrics: list[Artifact]) -> str:
    statuses = [
        _status_from_text(item, _safe_json(getattr(item, "parent_artifact_ids_json", None)), ["auc", "f1", "rmse", "mae", "accuracy", "decay"])
        for item in metrics
    ]
    return _worst_status(statuses)


def _status_from_text(artifact: Artifact, metadata: Any, keywords: list[str]) -> str:
    text = f"{artifact.kind} {artifact.uri} {json.dumps(metadata, default=str)}".lower()
    if any(keyword in text for keyword in keywords):
        if any(marker in text for marker in ["critical", "failed", "breach", "severe"]):
            return "critical"
        if any(marker in text for marker in ["warning", "degraded", "decay", "drift"]):
            return "warning"
        return "ok"
    return "unknown"


def _worst_status(statuses: list[str]) -> str:
    for candidate in ["critical", "warning", "ok"]:
        if candidate in statuses:
            return candidate
    return "unknown"


def _worse_status(current: str, candidate: str) -> str:
    return _worst_status([current, candidate])


def _version_label(artifact: Artifact) -> str:
    return f"artifact-{str(artifact.id)[:8]}"


def _uri_scheme(uri: str) -> str:
    if "://" not in uri:
        return "local"
    return uri.split("://", 1)[0]


def _safe_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


def _require_workspace_artifact(db: Session, *, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
    artifact = db.get(Artifact, artifact_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        raise ValueError("Artifact is not available in this workspace")
    return artifact


def _require_workspace_model(db: Session, *, workspace_id: uuid.UUID, model_id: uuid.UUID) -> ModelRegistryEntry:
    model = db.get(ModelRegistryEntry, model_id)
    if model is None or model.workspace_id != workspace_id:
        raise ValueError("Model is not available in this workspace")
    return model


def _safe_endpoint_url(endpoint_url: str | None) -> str | None:
    if not endpoint_url:
        return None
    return endpoint_url.split("?", 1)[0]
