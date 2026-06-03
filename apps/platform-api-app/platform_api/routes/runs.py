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
    get_workflow_spec_for_run,
    list_workflow_runs_for_workspace,
)
from platform_api.services.run_orchestration_service import create_orchestration_run_id
from platform_api.services.workflow_node_execution_service import (
    create_node_executions_for_run,
    list_node_executions_for_run,
    node_execution_to_dict,
    resume_run_from_failed_node,
    retry_node_execution,
)
from platform_api.services.workflow_queue_service import enqueue_workflow_run

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def _run_to_dict(run: WorkflowRun) -> dict:
    return {
        "id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "workspace_id": str(run.workspace_id),
        "flow_key": run.flow_key,
        "workflow_spec_id": str(run.workflow_spec_id) if run.workflow_spec_id else None,
        "workflow_version": run.workflow_version,
        "trigger_type": run.trigger_type,
        "input_artifact_ids": json.loads(run.input_artifact_ids_json) if run.input_artifact_ids_json else [],
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
    workflow_spec_id: str | None = None
    workflow_version: int | None = None
    trigger_type: str | None = "manual"
    input_artifact_ids: list[str] = Field(default_factory=list)


@router.post("", status_code=201)
async def trigger_run(
    body: TriggerRunRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    workflow_record = None
    workflow_spec = None
    if body.workflow_spec_id:
        workflow_record = get_workflow_spec_for_run(
            db,
            workflow_spec_id=body.workflow_spec_id,
            workspace_id=workspace.id,
            workflow_version=body.workflow_version,
        )
        workflow_spec = json.loads(workflow_record.spec_json)
    effective_parameters = {
        "requested_by": str(user.sub),
        "trigger_type": body.trigger_type or "manual",
        "input_artifact_ids": body.input_artifact_ids,
        **body.parameters,
    }
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
        workflow_spec_id=workflow_record.id if workflow_record else None,
        workflow_version=workflow_record.version if workflow_record else body.workflow_version,
        trigger_type=body.trigger_type,
        input_artifact_ids=body.input_artifact_ids,
    )
    create_node_executions_for_run(db, run=run, workflow_spec=workflow_spec)
    queue_result = enqueue_workflow_run(
        run_id=run.id,
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
        workflow_spec_id=workflow_record.id if workflow_record else None,
        trigger_type=body.trigger_type,
    )
    db.commit()
    db.refresh(run)
    result = _run_to_dict(run)
    result["queue"] = queue_result
    return result


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
    workflow_spec = None
    if original.workflow_spec_id:
        workflow_record = get_workflow_spec_for_run(
            db,
            workflow_spec_id=str(original.workflow_spec_id),
            workspace_id=workspace.id,
            workflow_version=original.workflow_version,
        )
        workflow_spec = json.loads(workflow_record.spec_json)
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
        workflow_spec_id=original.workflow_spec_id,
        workflow_version=original.workflow_version,
        trigger_type=original.trigger_type,
        input_artifact_ids=json.loads(original.input_artifact_ids_json) if original.input_artifact_ids_json else [],
    )
    create_node_executions_for_run(db, run=new_run, workflow_spec=workflow_spec)
    db.commit()
    db.refresh(new_run)
    return _run_to_dict(new_run)


@router.get("/{run_id}/nodes")
async def list_run_nodes(
    run_id: str,
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    run = get_run_by_id_for_workspace(db, run_id=run_id, workspace_id=workspace.id)
    nodes = list_node_executions_for_run(db, workflow_run_id=run.id)
    return {"items": [node_execution_to_dict(node) for node in nodes]}


class RetryNodeRequest(BaseModel):
    workspace_id: str


@router.post("/{run_id}/nodes/{node_id}/retry")
async def retry_run_node(
    run_id: str,
    node_id: str,
    body: RetryNodeRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    run = get_run_by_id_for_workspace_for_update(db, run_id=run_id, workspace_id=workspace.id)
    node = retry_node_execution(db, run=run, node_id=node_id)
    queue_result = enqueue_workflow_run(
        run_id=run.id,
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
        workflow_spec_id=run.workflow_spec_id,
        trigger_type=run.trigger_type,
    )
    db.commit()
    db.refresh(node)
    result = node_execution_to_dict(node)
    result["queue"] = queue_result
    return result


class ResumeRunRequest(BaseModel):
    workspace_id: str


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    body: ResumeRunRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    run = get_run_by_id_for_workspace_for_update(db, run_id=run_id, workspace_id=workspace.id)
    nodes = resume_run_from_failed_node(db, run=run)
    queue_result = enqueue_workflow_run(
        run_id=run.id,
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
        workflow_spec_id=run.workflow_spec_id,
        trigger_type=run.trigger_type,
    )
    db.commit()
    return {"resumed_nodes": [node_execution_to_dict(node) for node in nodes], "queue": queue_result}
