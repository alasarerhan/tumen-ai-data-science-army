from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_workspace_admin, require_workspace_member
from platform_api.db.session import get_db
from platform_api.services.modelops_service import (
    get_modelops_summary,
    record_deployment,
    record_monitor_snapshot,
    register_model,
)

router = APIRouter(prefix="/v1/modelops", tags=["modelops"])


class RegisterModelRequest(BaseModel):
    model_name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=80)
    stage: str = Field(default="candidate", max_length=40)
    artifact_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    approval_state: str = Field(default="not_reviewed", max_length=50)
    model_card: dict[str, Any] | None = None


class MonitorSnapshotRequest(BaseModel):
    model_id: uuid.UUID
    monitor_type: str = Field(min_length=1, max_length=80)
    status: str = Field(default="unknown", max_length=50)
    artifact_id: uuid.UUID | None = None
    metric_name: str | None = Field(default=None, max_length=120)
    metric_value: float | None = None
    threshold_value: float | None = None
    baseline: dict[str, Any] | None = None
    remediation_workflow: str | None = Field(default=None, max_length=200)


class DeploymentRecordRequest(BaseModel):
    model_id: uuid.UUID
    environment: str = Field(min_length=1, max_length=80)
    status: str = Field(default="planned", max_length=50)
    endpoint_url: str | None = None
    deployed_at: datetime | None = None
    rollback_model_id: uuid.UUID | None = None
    rollback_notes: str | None = None
    health_status: str = Field(default="unknown", max_length=50)
    last_health_check_at: datetime | None = None


@router.get("/summary")
async def modelops_summary(
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    return get_modelops_summary(db, workspace_id=workspace.id)


@router.post("/registry", status_code=201)
async def modelops_register_model(
    payload: RegisterModelRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    try:
        entry = register_model(
            db,
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            model_name=payload.model_name,
            version=payload.version,
            stage=payload.stage,
            artifact_id=payload.artifact_id,
            workflow_run_id=payload.workflow_run_id,
            owner_user_id=user.id,
            approval_state=payload.approval_state,
            model_card=payload.model_card,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Model registry entry could not be created"
        ) from exc
    return {"model_id": str(entry.id), "status": "registered"}


@router.post("/monitors", status_code=201)
async def modelops_record_monitor(
    payload: MonitorSnapshotRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    try:
        snapshot = record_monitor_snapshot(
            db,
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            model_id=payload.model_id,
            monitor_type=payload.monitor_type,
            status=payload.status,
            artifact_id=payload.artifact_id,
            metric_name=payload.metric_name,
            metric_value=payload.metric_value,
            threshold_value=payload.threshold_value,
            baseline=payload.baseline,
            owner_user_id=user.id,
            remediation_workflow=payload.remediation_workflow,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"monitor_id": str(snapshot.id), "status": "recorded"}


@router.post("/deployments", status_code=201)
async def modelops_record_deployment(
    payload: DeploymentRecordRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    try:
        deployment = record_deployment(
            db,
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            model_id=payload.model_id,
            environment=payload.environment,
            status=payload.status,
            endpoint_url=payload.endpoint_url,
            deployed_at=payload.deployed_at,
            rollback_model_id=payload.rollback_model_id,
            rollback_notes=payload.rollback_notes,
            health_status=payload.health_status,
            last_health_check_at=payload.last_health_check_at,
            created_by_user_id=user.id,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deployment_id": str(deployment.id), "status": "recorded"}
