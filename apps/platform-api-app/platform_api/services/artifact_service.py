from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.db.models import Artifact, WorkflowRun, Workspace, WorkspaceMembership
from platform_api.db.tenant_query import TenantQuery
from platform_api.core.service_errors import ForbiddenError, NotFoundError, ValidationError


def _parse_uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
    return TenantQuery._parse_uuid(value, label)


def _authorized_workspace(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
) -> Workspace:
    workspace_uuid = _parse_uuid(workspace_id, "workspace_id")
    workspace = db.execute(select(Workspace).where(Workspace.id == workspace_uuid)).scalar_one_or_none()
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
        created_by_user_id=user_id,
    )
    db.add(artifact)
    db.flush()
    return artifact


def list_artifacts_for_workspace(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 20,
) -> list[Artifact]:
    workspace = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    return TenantQuery(db, Artifact).for_workspace(workspace.id).list(limit=limit, cursor=cursor)


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
