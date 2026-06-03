from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from platform_api.authz.policy import can_admin_workspace
from platform_api.db.models import WorkflowSpec, Workspace, WorkspaceMembership
from platform_api.db.tenant_query import TenantQuery
from platform_api.core.service_errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from platform_api.services.workflow_chain_validator import inspect_workflow_spec
from platform_api.services.workflow_ir_service import validate_workflow_ir_v2
from platform_api.services.quota_service import enforce_tenant_write_quota

logger = logging.getLogger(__name__)

WorkflowSpecStatus = Literal["draft", "published", "archived"]

_VALID_STATUSES: set[str] = {"draft", "published", "archived"}
_LEGACY_TOOL_AGENT_MAP: dict[str, str] = {
    "data_load": "DataLoaderToolsAgent",
    "data_clean": "DataCleaningAgent",
    "feature_engineering": "FeatureEngineeringAgent",
    "model_train": "H2OMLAgent",
    "eda": "EDAToolsAgent",
    "report": "NarrativeAgent",
}


def _normalize_spec_for_validation(spec: dict, *, workflow_name: str | None = None) -> dict:
    effective_spec = spec if spec.get("name") or not workflow_name else {**spec, "name": workflow_name}
    steps = effective_spec.get("steps")
    if not isinstance(steps, list):
        return effective_spec
    normalized_steps: list[dict] = []
    changed = False
    previous_id: str | None = None
    for step in steps:
        if not isinstance(step, dict):
            normalized_steps.append(step)
            continue
        normalized = dict(step)
        tool = str(normalized.get("tool") or "").strip()
        if not normalized.get("agent") and tool in _LEGACY_TOOL_AGENT_MAP:
            normalized["agent"] = _LEGACY_TOOL_AGENT_MAP[tool]
            changed = True
        if previous_id and not normalized.get("depends_on"):
            normalized["depends_on"] = [previous_id]
            changed = True
        previous_id = str(normalized.get("id") or previous_id)
        normalized_steps.append(normalized)
    if not changed:
        return effective_spec
    return {**effective_spec, "steps": normalized_steps}


def build_workflow_validation_summary(spec: dict, *, workflow_name: str | None = None) -> dict:
    effective_spec = _normalize_spec_for_validation(spec, workflow_name=workflow_name)
    inspection = inspect_workflow_spec(effective_spec)
    errors = inspection.get("errors", [])
    warnings = inspection.get("warnings", [])
    if effective_spec.get("ir_version") == "2.0":
        ir_inspection = validate_workflow_ir_v2(effective_spec)
        errors = [*errors, *ir_inspection["errors"]]
        warnings = [*warnings, *ir_inspection["warnings"]]
    if errors:
        status = "invalid"
    elif warnings:
        status = "advisory"
    else:
        status = "safe"
    return {
        "status": status,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": [str(error.get("message", "")).strip() for error in errors if error.get("message")],
        "warnings": [str(warning.get("message", "")).strip() for warning in warnings if warning.get("message")],
    }


def _lock_workflow_version_counter(db: Session, *, workspace_id: uuid.UUID, name: str) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:workflow_key))"),
        {"workflow_key": f"{workspace_id}:{name}"},
    )


def _authorized_workspace(db: Session, *, workspace_id: str, user_id: uuid.UUID) -> tuple[Workspace, WorkspaceMembership]:
    workspace_uuid = TenantQuery._parse_uuid(workspace_id, "workspace_id")
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

    return workspace, membership


def _validate_spec(spec: dict, *, workflow_name: str | None = None) -> None:
    errors = build_workflow_validation_summary(spec, workflow_name=workflow_name)["errors"]
    if errors:
        raise ValidationError(" ".join(errors))


def create_workflow_spec_version(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
    name: str,
    spec: dict,
    publish: bool,
) -> WorkflowSpec:
    workspace, membership = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    _validate_spec(spec, workflow_name=name)
    if publish and not can_admin_workspace(membership.role):
        raise ForbiddenError("Workspace admin/owner role required for publish")

    enforce_tenant_write_quota(db, str(workspace.tenant_id))
    _lock_workflow_version_counter(db, workspace_id=workspace.id, name=name)

    current_max_version = db.execute(
        select(func.max(WorkflowSpec.version))
        .where(
            WorkflowSpec.workspace_id == workspace.id,
            WorkflowSpec.name == name,
        )
        .with_for_update()
    ).scalar_one_or_none()

    next_version = int(current_max_version or 0) + 1
    status = "published" if publish else "draft"

    record = WorkflowSpec(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        name=name,
        version=next_version,
        status=status,
        spec_json=json.dumps(spec),
        created_by_user_id=user_id,
    )
    db.add(record)
    db.flush()
    return record


def get_workflow_spec_for_workspace(
    db: Session,
    *,
    workflow_id: str,
    workspace_id: str,
    user_id: uuid.UUID,
) -> WorkflowSpec:
    """Get a workflow spec by ID, ensuring it belongs to the specified workspace.

    Security: workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities.
    """
    workspace, _membership = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    return TenantQuery(db, WorkflowSpec).for_workspace(workspace.id).get(workflow_id)


def get_latest_workflow_spec(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
    name: str,
) -> WorkflowSpec | None:
    workspace, _membership = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    return db.execute(
        select(WorkflowSpec)
        .where(
            WorkflowSpec.workspace_id == workspace.id,
            WorkflowSpec.name == name,
        )
        .order_by(WorkflowSpec.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def _auto_archive_published(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    name: str,
    exclude_id: uuid.UUID,
) -> int:
    """Set all currently-published versions of *name* in *workspace_id* to
    'archived', except the record identified by *exclude_id*.

    Returns the count of records archived.
    """
    rows = list(
        db.execute(
            select(WorkflowSpec).where(
                WorkflowSpec.workspace_id == workspace_id,
                WorkflowSpec.name == name,
                WorkflowSpec.status == "published",
                WorkflowSpec.id != exclude_id,
            )
        ).scalars()
    )
    for row in rows:
        row.status = "archived"
        db.add(row)
    db.flush()
    return len(rows)


def publish_workflow_spec(
    db: Session,
    *,
    workflow_id: str,
    workspace_id: str,
    user_id: uuid.UUID,
) -> WorkflowSpec:
    workspace, membership = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    if not can_admin_workspace(membership.role):
        raise ForbiddenError("Workspace admin/owner role required for publish")

    enforce_tenant_write_quota(db, str(workspace.tenant_id))
    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if record.status == "archived":
        raise ConflictError("Cannot publish an archived spec; create a new version instead")

    if record.status != "published":
        record.status = "published"
        db.add(record)
    db.flush()
    if hasattr(db, "refresh"):
        try:
            db.refresh(record)
        except Exception:
            logger.debug("Skipping workflow refresh after publish", exc_info=True)

    _auto_archive_published(db, workspace_id=workspace.id, name=record.name, exclude_id=record.id)

    return record


def archive_workflow_spec(
    db: Session,
    *,
    workflow_id: str,
    workspace_id: str,
    user_id: uuid.UUID,
) -> WorkflowSpec:
    """Explicitly archive a draft or published workflow spec version.
    Only workspace admins/owners may archive.
    """
    workspace, membership = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)
    if not can_admin_workspace(membership.role):
        raise ForbiddenError("Workspace admin/owner role required for archive")

    record = get_workflow_spec_for_workspace(
        db,
        workflow_id=workflow_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    if record.status == "archived":
        raise ConflictError("Spec is already archived")

    record.status = "archived"
    db.add(record)
    db.flush()
    return record


def list_workflow_specs(
    db: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
    name: str | None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> list[WorkflowSpec]:
    workspace, _membership = _authorized_workspace(db, workspace_id=workspace_id, user_id=user_id)

    if status is not None and status not in _VALID_STATUSES:
        raise ValidationError("Invalid status filter value")

    query = TenantQuery(db, WorkflowSpec).for_workspace(workspace.id)
    if name or status:
        stmt = select(WorkflowSpec).where(WorkflowSpec.workspace_id == workspace.id)
        if name:
            stmt = stmt.where(WorkflowSpec.name == name)
        if status:
            stmt = stmt.where(WorkflowSpec.status == status)
        if cursor:
            try:
                cursor_uuid = uuid.UUID(cursor)
                cursor_row = db.execute(
                    select(WorkflowSpec.created_at).where(
                        WorkflowSpec.workspace_id == workspace.id,
                        WorkflowSpec.id == cursor_uuid,
                    )
                ).one_or_none()
                if cursor_row is not None:
                    cursor_created_at = cursor_row[0]
                    stmt = stmt.where(
                        or_(
                            WorkflowSpec.created_at < cursor_created_at,
                            and_(
                                WorkflowSpec.created_at == cursor_created_at,
                                WorkflowSpec.id < cursor_uuid,
                            ),
                        )
                    )
            except ValueError:
                pass
        stmt = stmt.order_by(WorkflowSpec.created_at.desc(), WorkflowSpec.id.desc()).limit(limit + 1)
        return list(db.execute(stmt).scalars())

    return query.list(limit=limit, cursor=cursor)
