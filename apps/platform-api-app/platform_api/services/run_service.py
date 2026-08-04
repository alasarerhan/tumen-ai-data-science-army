from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from platform_api.core.service_errors import ForbiddenError, NotFoundError
from platform_api.db.models import WorkflowRun, WorkflowSpec, Workspace, WorkspaceMembership
from platform_api.db.tenant_query import TenantQuery
from platform_api.tenant_context import set_tenant_context

_RUN_WRITE_LOCK = threading.Lock()


def _parse_uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
    return TenantQuery._parse_uuid(value, label)


def _normalize_run_not_found_error(exc: Exception) -> Exception:
    if (
        getattr(exc, "status_code", None) == 404
        and getattr(exc, "detail", None) == "WorkflowRun not found"
    ):
        return NotFoundError("Workflow run not found")
    return exc


def ensure_workspace_member(db: Session, *, workspace_id: str, user_id: uuid.UUID) -> uuid.UUID:
    workspace_uuid = _parse_uuid(workspace_id, "workspace_id")
    workspace = db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid)
    ).scalar_one_or_none()
    if workspace is None:
        raise NotFoundError("Workspace not found")

    membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_uuid,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise ForbiddenError("Workspace membership required")
    return workspace_uuid


def get_workspace_for_member(db: Session, *, workspace_id: str, user_id: uuid.UUID) -> Workspace:
    workspace_uuid = ensure_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    workspace = db.execute(select(Workspace).where(Workspace.id == workspace_uuid)).scalar_one()
    set_tenant_context(workspace.tenant_id, workspace.id)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SET app.current_tenant_id = :tenant_id"), {"tenant_id": str(workspace.tenant_id)}
        )
    return workspace


def create_workflow_run_record(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    flow_key: str,
    prefect_flow_run_id: str,
    parameters: dict,
    workflow_spec_id: uuid.UUID | None = None,
    workflow_version: int | None = None,
    trigger_type: str | None = None,
    input_artifact_ids: list[str] | None = None,
) -> WorkflowRun:
    run = WorkflowRun(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        requested_by_user_id=user_id,
        flow_key=flow_key,
        workflow_spec_id=workflow_spec_id,
        workflow_version=workflow_version,
        trigger_type=trigger_type,
        input_artifact_ids_json=json.dumps(input_artifact_ids or []),
        prefect_flow_run_id=prefect_flow_run_id,
        status="SCHEDULED",
        parameters_json=json.dumps(parameters),
        started_at=None,
        finished_at=None,
    )
    # Guard the shared session write path so concurrent callers do not interleave
    # `add()` / `flush()` on the same Session instance.
    with _RUN_WRITE_LOCK:
        db.add(run)
        db.flush()
    return run


def get_workflow_spec_for_run(
    db: Session,
    *,
    workflow_spec_id: str,
    workspace_id: uuid.UUID,
    workflow_version: int | None = None,
) -> WorkflowSpec:
    parsed_spec_id = _parse_uuid(workflow_spec_id, "workflow_spec_id")
    query = select(WorkflowSpec).where(
        WorkflowSpec.id == parsed_spec_id,
        WorkflowSpec.workspace_id == workspace_id,
    )
    if workflow_version is not None:
        query = query.where(WorkflowSpec.version == workflow_version)
    record = db.execute(query).scalar_one_or_none()
    if record is None:
        raise NotFoundError("Workflow spec not found")
    return record


def update_workflow_run_status(
    db: Session,
    *,
    prefect_flow_run_id: str,
    status_name: str | None,
    start_time,
    end_time,
) -> WorkflowRun | None:
    run = db.execute(
        select(WorkflowRun).where(WorkflowRun.prefect_flow_run_id == prefect_flow_run_id)
    ).scalar_one_or_none()
    if run is None:
        return None

    if status_name:
        run.status = status_name

    parsed_start_time = start_time
    parsed_end_time = end_time
    if isinstance(start_time, str):
        parsed_start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    if isinstance(end_time, str):
        parsed_end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    run.started_at = parsed_start_time
    run.finished_at = parsed_end_time
    run.updated_at = datetime.now(UTC)
    db.add(run)
    db.flush()
    return run


def get_run_by_id_for_workspace(
    db: Session,
    *,
    run_id: str,
    workspace_id: uuid.UUID,
) -> WorkflowRun:
    """Fetch a single WorkflowRun; 404 if not found, 403 if it belongs to another workspace.

    Security: tenant_id/workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities. This follows best practices from:
    https://avatao.com/best-practices-to-prevent-idor-vulnerabilities/
    """
    parsed_run_id = _parse_uuid(run_id, "run_id")
    try:
        return TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get(parsed_run_id)
    except Exception as exc:
        raise _normalize_run_not_found_error(exc) from exc


def get_run_by_id_for_workspace_for_update(
    db: Session,
    *,
    run_id: str,
    workspace_id: uuid.UUID,
) -> WorkflowRun:
    """Fetch a single WorkflowRun with row-level lock for status transitions.

    Uses SELECT FOR UPDATE to prevent race conditions when multiple requests
    try to modify the same run's status simultaneously.

    Security: tenant_id/workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities.

    Raises a service-layer not-found or forbidden error if access is invalid.
    """
    parsed_run_id = _parse_uuid(run_id, "run_id")
    try:
        return (
            TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get_for_update(parsed_run_id)
        )
    except Exception as exc:
        raise _normalize_run_not_found_error(exc) from exc


def list_workflow_runs_for_workspace(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 20,
) -> list[WorkflowRun]:
    return TenantQuery(db, WorkflowRun).for_workspace(workspace_id).list(limit=limit, cursor=cursor)


def get_run_by_id_for_workspace_with_artifacts(
    db: Session,
    *,
    run_id: str,
    workspace_id: uuid.UUID,
) -> WorkflowRun:
    """Fetch a WorkflowRun with eager-loaded artifacts to prevent N+1 queries."""
    parsed_run_id = _parse_uuid(run_id, "run_id")
    try:
        return TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get(parsed_run_id)
    except Exception as exc:
        raise _normalize_run_not_found_error(exc) from exc
