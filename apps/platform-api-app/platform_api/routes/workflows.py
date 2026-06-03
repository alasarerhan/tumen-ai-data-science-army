from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.authz.dependencies import require_workspace_admin, require_workspace_member
from platform_api.core.etag import compute_etag, validate_etag
from platform_api.core.service_errors import ValidationError
from platform_api.db.session import get_db
from platform_api.schemas.pagination import build_paginated_response, MAX_PAGE_SIZE
from platform_api.schemas.workflows import CreateWorkflowSpecRequest
from platform_api.services.identity_service import get_or_create_user
from platform_api.services.workflow_service import (
    archive_workflow_spec,
    build_workflow_validation_summary,
    create_workflow_spec_version,
    get_latest_workflow_spec,
    get_workflow_spec_for_workspace,
    list_workflow_specs,
    publish_workflow_spec,
)
from platform_api.services.workflow_chain_validator import (
    get_workflow_agent_catalog,
    get_workflow_chain_ruleset,
)

router = APIRouter(prefix="/v1/workflows", tags=["workflows"])


def _serialize_workflow_record(record, *, include_etag: bool = False) -> dict:
    spec = json.loads(record.spec_json)
    payload = {
        "id": str(record.id),
        "workspace_id": str(record.workspace_id),
        "tenant_id": str(record.tenant_id),
        "name": record.name,
        "version": record.version,
        "status": record.status,
        "spec": spec,
        "validation_summary": build_workflow_validation_summary(spec, workflow_name=record.name),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
    if include_etag:
        payload["_etag"] = compute_etag(record)
    return payload


@router.get("/chain-rules")
async def get_workflow_chain_rules(
    context: dict = Depends(require_workspace_member),
) -> dict:
    return {
        "workspace_id": str(context["workspace"].id),
        "ruleset": get_workflow_chain_ruleset(),
        "catalog": get_workflow_agent_catalog(),
    }


@router.post("")
async def create_workflow_spec(
    payload: CreateWorkflowSpecRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    # workspace_id comes from body — membership + role check happens inside service.
    user = get_or_create_user(db, principal)
    record = create_workflow_spec_version(
        db,
        workspace_id=payload.workspace_id,
        user_id=user.id,
        name=payload.name,
        spec=payload.spec,
        publish=payload.publish,
    )
    db.commit()
    return _serialize_workflow_record(record)


@router.get("")
async def get_workflow_specs(
    name: str | None = None,
    status: str | None = None,
    cursor: Optional[str] = Query(default=None, description="Pagination cursor (workflow ID)"),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    user = context["user"]
    workspace = context["workspace"]
    records = list_workflow_specs(
        db,
        workspace_id=str(workspace.id),
        user_id=user.id,
        name=name,
        status=status,
        cursor=cursor,
        limit=limit,
    )
    paginated = build_paginated_response(records, limit)
    return {
        "items": [_serialize_workflow_record(record) for record in paginated["items"]],
        "next_cursor": paginated["next_cursor"],
        "has_more": paginated["has_more"],
    }


@router.get("/latest")  # GET /v1/workflows/latest — workspace member required
async def get_latest_workflow(
    name: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    user = context["user"]
    workspace = context["workspace"]
    record = get_latest_workflow_spec(
        db,
        workspace_id=str(workspace.id),
        user_id=user.id,
        name=name,
    )
    if record is None:
        return {"item": None}

    return {"item": _serialize_workflow_record(record)}


@router.get("/{workflow_id}")
async def get_workflow_by_id(
    workflow_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    user = context["user"]
    workspace = context["workspace"]
    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )
    return _serialize_workflow_record(record, include_etag=True)


@router.post("/{workflow_id}/publish")
async def publish_workflow(
    workflow_id: str,
    context: dict = Depends(require_workspace_admin),
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> dict:
    user = context["user"]
    workspace = context["workspace"]
    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )
    if if_match:
        validate_etag(record, if_match)
    record = publish_workflow_spec(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )
    db.commit()
    etag = compute_etag(record)
    spec = json.loads(record.spec_json)
    return {
        "id": str(record.id),
        "name": record.name,
        "version": record.version,
        "status": record.status,
        "validation_summary": build_workflow_validation_summary(spec, workflow_name=record.name),
        "_etag": etag,
    }


@router.post("/{workflow_id}/archive")
async def archive_workflow(
    workflow_id: str,
    context: dict = Depends(require_workspace_admin),
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> dict:
    """Archive a draft or published workflow spec version."""
    user = context["user"]
    workspace = context["workspace"]
    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )
    if if_match:
        validate_etag(record, if_match)
    record = archive_workflow_spec(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )
    db.commit()
    etag = compute_etag(record)
    spec = json.loads(record.spec_json)
    return {
        "id": str(record.id),
        "name": record.name,
        "version": record.version,
        "status": record.status,
        "validation_summary": build_workflow_validation_summary(spec, workflow_name=record.name),
        "_etag": etag,
    }


class CreateScheduleRequest(BaseModel):
    cron: str
    timezone: Optional[str] = "UTC"


@router.post("/{workflow_id}/schedule")
async def create_schedule(
    workflow_id: str,
    body: CreateScheduleRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a scheduled deployment for a workflow."""
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    user = context["user"]
    workspace = context["workspace"]

    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )

    scheduler = WorkflowSchedulerService(db)
    result = await scheduler.create_scheduled_deployment(
        workflow_spec=record,
        cron=body.cron,
        timezone=body.timezone or "UTC",
    )

    return result


@router.get("/schedules")
async def list_schedules(
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    """List all scheduled deployments for the workspace."""
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    workspace = context["workspace"]
    scheduler = WorkflowSchedulerService(db)
    deployments = await scheduler.list_scheduled_deployments(
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )

    return {"items": deployments}


@router.get("/{workflow_id}/schedule")
async def get_workflow_schedule(
    workflow_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    """Get the schedule for a specific workflow."""
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    user = context["user"]
    workspace = context["workspace"]

    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )

    scheduler = WorkflowSchedulerService(db)
    deployments = await scheduler.list_scheduled_deployments(
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )

    for dep in deployments:
        if dep.get("workflow_spec_id") == str(record.id):
            return dep

    return {"error": "No schedule found"}


@router.post("/schedules/{deployment_id}/pause")
async def pause_schedule(
    deployment_id: str,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Pause a scheduled deployment."""
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    workspace = context["workspace"]
    scheduler = WorkflowSchedulerService(db)
    result = await scheduler.pause_scheduled_deployment(
        deployment_id,
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )
    return result


@router.post("/schedules/{deployment_id}/resume")
async def resume_schedule(
    deployment_id: str,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Resume a paused scheduled deployment."""
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    workspace = context["workspace"]
    scheduler = WorkflowSchedulerService(db)
    result = await scheduler.resume_scheduled_deployment(
        deployment_id,
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )
    return result


@router.post("/{workflow_id}/trigger")
async def trigger_workflow(
    workflow_id: str,
    body: Optional[dict] = None,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    """Manually trigger a workflow run."""
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    user = context["user"]
    workspace = context["workspace"]

    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=str(workspace.id),
        user_id=user.id,
    )
    spec = json.loads(record.spec_json)
    validation_summary = build_workflow_validation_summary(spec, workflow_name=record.name)
    if validation_summary["status"] == "invalid":
        raise ValidationError("Workflow contains invalid agent chains and cannot be triggered.")

    scheduler = WorkflowSchedulerService(db)
    parameters = body.get("parameters", {}) if body else {}
    result = await scheduler.trigger_scheduled_workflow(
        workflow_spec_id=record.id,
        parameters=parameters,
    )

    return result
