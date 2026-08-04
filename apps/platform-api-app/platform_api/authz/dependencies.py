from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.authz.policy import can_admin_tenant, can_admin_workspace
from platform_api.db.models import TenantMembership, Workspace, WorkspaceMembership
from platform_api.db.session import get_db
from platform_api.services.identity_service import get_or_create_user
from platform_api.tenant_context import set_tenant_context


def _get_workspace_and_membership(
    workspace_id: str,
    principal: Principal,
    db: Session,
) -> dict:
    """Shared helper: resolve workspace + membership for *workspace_id* query param.

    Returns ``{"user", "workspace", "membership"}``.
    Raises 400 on bad UUID, 404 if workspace missing, 403 if not a member.

    Security: Sets tenant context for PostgreSQL RLS enforcement.
    """
    user = get_or_create_user(db, principal)

    try:
        workspace_uuid = uuid.UUID(workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid workspace_id") from exc

    workspace = db.execute(
        select(Workspace).where(Workspace.id == workspace_uuid)
    ).scalar_one_or_none()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=403, detail="Workspace membership required")

    set_tenant_context(workspace.tenant_id, workspace.id)

    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SET app.current_tenant_id = :tenant_id"), {"tenant_id": str(workspace.tenant_id)}
        )

    return {"user": user, "workspace": workspace, "membership": membership}


async def require_workspace_member(
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    """FastAPI dependency — requires any workspace membership (owner/admin/member).

    Returns ``{"user", "workspace", "membership"}``.
    """
    return _get_workspace_and_membership(workspace_id, principal, db)


async def require_workspace_admin(
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    """FastAPI dependency — requires workspace admin or owner role.

    Returns ``{"user", "workspace", "membership"}``.
    Raises 403 if the caller is only a ``member``.
    """
    context = _get_workspace_and_membership(workspace_id, principal, db)
    if not can_admin_workspace(context["membership"].role):
        raise HTTPException(
            status_code=403,
            detail="Workspace admin or owner role required",
        )
    return context


async def require_tenant_admin(
    tenant_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    """FastAPI dependency — requires tenant admin or owner role.

    Security: Validates tenant membership and admin role before allowing
    access to tenant-level administrative functions.

    Returns ``{"user", "tenant_id", "membership"}``.
    Raises 403 if the caller is not a tenant admin/owner.
    """
    user = get_or_create_user(db, principal)

    try:
        tenant_uuid = uuid.UUID(tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid tenant_id") from exc

    membership = db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_uuid,
            TenantMembership.user_id == user.id,
        )
    ).scalar_one_or_none()

    if membership is None:
        raise HTTPException(status_code=403, detail="Tenant membership required")

    if not can_admin_tenant(membership.role):
        raise HTTPException(
            status_code=403,
            detail="Tenant admin or owner role required",
        )

    set_tenant_context(tenant_uuid)

    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SET app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_uuid)},
        )

    return {"user": user, "tenant_id": tenant_uuid, "membership": membership}
