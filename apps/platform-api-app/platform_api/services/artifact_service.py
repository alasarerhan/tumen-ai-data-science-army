from __future__ import annotations

import json
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from platform_api.core.service_errors import ForbiddenError, NotFoundError, ValidationError
from platform_api.db.models import Artifact, WorkflowRun, Workspace, WorkspaceMembership
from platform_api.db.tenant_query import TenantQuery


def _parse_uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
    return TenantQuery._parse_uuid(value, label)


def _authorized_workspace(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
) -> Workspace:
    workspace_uuid = _parse_uuid(workspace_id, "workspace_id")
    workspace = db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid)
    ).scalar_one_or_none()
    if workspace is None:
        raise NotFoundError("Workspace not found")

    membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise ForbiddenError("Workspace membership required")

    return workspace


def create_artifact_record(
    db: Session,
    *,
    workspace_id: str,
    workflow_run_id: str | None,
    kind: str,
    uri: str,
    user_id: uuid.UUID,
    produced_by_node_id: str | None = None,
    parent_artifact_ids: list[str] | None = None,
) -> Artifact:
    workspace = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)

    parsed_workflow_run_id = None
    if workflow_run_id:
        run = TenantQuery(db, WorkflowRun).for_workspace(workspace.id).get_or_none(workflow_run_id)
        if run is None:
            raise ValidationError("workflow_run_id not in workspace")
        parsed_workflow_run_id = run.id

    artifact = Artifact(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=parsed_workflow_run_id,
        kind=kind,
        uri=uri,
        produced_by_node_id=produced_by_node_id,
        parent_artifact_ids_json=json.dumps(parent_artifact_ids or []),
        created_by_user_id=user_id,
    )
    db.add(artifact)
    db.flush()
    return artifact


def create_system_artifact_record(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    workflow_run_id: uuid.UUID | None,
    kind: str,
    uri: str,
    produced_by_node_id: str | None = None,
    parent_artifact_ids: list[str] | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> Artifact:
    """Create an artifact from a trusted worker/system path.

    API callers must use ``create_artifact_record`` so workspace membership is
    enforced. Worker code already executes inside a tenant/workspace-scoped run,
    so it passes explicit scope IDs and does not need a user membership lookup.
    """
    artifact = Artifact(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        workflow_run_id=workflow_run_id,
        kind=kind,
        uri=uri,
        produced_by_node_id=produced_by_node_id,
        parent_artifact_ids_json=json.dumps(parent_artifact_ids or []),
        created_by_user_id=created_by_user_id,
    )
    db.add(artifact)
    db.flush()
    return artifact


def get_artifact_parent_ids(artifact: Artifact) -> list[str]:
    if not artifact.parent_artifact_ids_json:
        return []
    try:
        values = json.loads(artifact.parent_artifact_ids_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if value is not None]


def list_artifacts_for_workspace(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 20,
    workflow_run_id: str | None = None,
    kind: str | None = None,
) -> list[Artifact]:
    workspace = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    stmt = select(Artifact).where(
        Artifact.workspace_id == workspace.id,
        Artifact.tenant_id == workspace.tenant_id,
    )

    if kind:
        stmt = stmt.where(Artifact.kind == kind)

    if workflow_run_id:
        stmt = stmt.where(
            Artifact.workflow_run_id == _parse_uuid(workflow_run_id, "workflow_run_id")
        )

    stmt = stmt.order_by(Artifact.created_at.desc(), Artifact.id.desc())

    if cursor:
        cursor_uuid = _parse_uuid(cursor, "cursor")
        cursor_stmt = select(Artifact).where(
            Artifact.id == cursor_uuid,
            Artifact.workspace_id == workspace.id,
            Artifact.tenant_id == workspace.tenant_id,
        )
        cursor_row = db.execute(cursor_stmt).scalar_one_or_none()
        if cursor_row is not None:
            stmt = stmt.where(
                or_(
                    Artifact.created_at < cursor_row.created_at,
                    and_(Artifact.created_at == cursor_row.created_at, Artifact.id < cursor_uuid),
                )
            )

    return list(db.execute(stmt.limit(limit + 1)).scalars().all())


def get_artifact_for_workspace_with_run(
    db: Session,
    *,
    artifact_id: str,
    workspace_id: str,
    user_id: uuid.UUID,
) -> Artifact:
    """Get an artifact with eager-loaded workflow_run to prevent N+1 queries."""
    workspace = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    parsed_artifact_id = _parse_uuid(artifact_id, "artifact_id")
    artifact = TenantQuery(db, Artifact).for_workspace(workspace.id).get(parsed_artifact_id)
    if artifact.tenant_id != workspace.tenant_id:
        raise ForbiddenError("Artifact access denied")
    return artifact


def get_artifact_for_workspace(
    db: Session,
    *,
    artifact_id: str,
    workspace_id: str,
    user_id: uuid.UUID,
) -> Artifact:
    """Get an artifact by ID, ensuring it belongs to the specified workspace.

    Security: workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities.
    """
    workspace = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    parsed_artifact_id = _parse_uuid(artifact_id, "artifact_id")
    artifact = TenantQuery(db, Artifact).for_workspace(workspace.id).get(parsed_artifact_id)
    if artifact.tenant_id != workspace.tenant_id:
        raise ForbiddenError("Artifact access denied")
    return artifact
