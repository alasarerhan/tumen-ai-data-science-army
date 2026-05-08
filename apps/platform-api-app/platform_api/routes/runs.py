from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_workspace_member
from platform_api.core.etag import compute_etag, validate_etag
from platform_api.db.models import WorkflowRun
from platform_api.db.session import get_db
from platform_api.schemas.pagination import build_paginated_response, MAX_PAGE_SIZE
from platform_api.services.run_service import (
    create_workflow_run_record,
    get_run_by_id_for_workspace,
    get_run_by_id_for_workspace_for_update,
    list_workflow_runs_for_workspace,
)
from platform_api.services.run_orchestration_service import create_orchestration_run_id

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def _run_to_dict(run: WorkflowRun) -> dict:
    return {
        "id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "workspace_id": str(run.workspace_id),
        "flow_key": run.flow_key,
        "prefect_flow_run_id": run.prefect_flow_run_id,
        "status": run.status,
        "parameters": json.loads(run.parameters_json) if run.parameters_json else {},
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@router.get("")
async def list_runs(
    workspace_id: str,
    cursor: Optional[str] = Query(default=None, description="Pagination cursor (run ID)"),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    runs = list_workflow_runs_for_workspace(
        db, workspace_id=workspace.id, cursor=cursor, limit=limit
    )
    paginated = build_paginated_response(runs, limit)
    return {
        "items": [_run_to_dict(r) for r in paginated["items"]],
        "next_cursor": paginated["next_cursor"],
        "has_more": paginated["has_more"],
    }


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    run = get_run_by_id_for_workspace(db, run_id=run_id, workspace_id=workspace.id)
    etag = compute_etag(run)
    result = _run_to_dict(run)
    result["_etag"] = etag
    return result


class TriggerRunRequest(BaseModel):
    workspace_id: str
    flow_key: str = "default"
    parameters: dict = Field(default_factory=dict)


@router.post("", status_code=201)
async def trigger_run(
    body: TriggerRunRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    effective_parameters = {"requested_by": str(user.sub), **body.parameters}
    flow_run_id = await create_orchestration_run_id(
        flow_key=body.flow_key,
        parameters=effective_parameters,
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        tenant_id=str(workspace.tenant_id),
    )
    run = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key=body.flow_key,
        prefect_flow_run_id=flow_run_id,
        parameters=effective_parameters,
    )
    db.commit()
    db.refresh(run)
    return _run_to_dict(run)


class UpdateRunStatusRequest(BaseModel):
    workspace_id: str


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    body: UpdateRunStatusRequest,
    context: dict = Depends(require_workspace_member),
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
) -> dict:
    """Cancel a workflow run.
    
    Uses row-level locking (SELECT FOR UPDATE) to prevent race conditions
    when multiple concurrent requests attempt to modify the same run.
    """
    workspace = context["workspace"]
    # Use FOR UPDATE to prevent race conditions on status transitions
    run = get_run_by_id_for_workspace_for_update(
        db, run_id=run_id, workspace_id=workspace.id
    )
    if if_match:
        validate_etag(run, if_match)
    if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=409, detail=f"Run is already in terminal state: {run.status}")
    run.status = "CANCELLED"
    db.add(run)
    db.commit()
    db.refresh(run)
    etag = compute_etag(run)
    result = _run_to_dict(run)
    result["_etag"] = etag
    return result


@router.post("/{run_id}/retry", status_code=201)
async def retry_run(
    run_id: str,
    body: UpdateRunStatusRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    original = get_run_by_id_for_workspace(db, run_id=run_id, workspace_id=workspace.id)
    effective_parameters = json.loads(original.parameters_json) if original.parameters_json else {}
    effective_parameters = {"requested_by": str(user.sub), **effective_parameters}
    flow_run_id = await create_orchestration_run_id(
        flow_key=original.flow_key,
        parameters=effective_parameters,
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        tenant_id=str(workspace.tenant_id),
    )
    new_run = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key=original.flow_key,
        prefect_flow_run_id=flow_run_id,
        parameters=effective_parameters,
    )
    db.commit()
    db.refresh(new_run)
    return _run_to_dict(new_run)
