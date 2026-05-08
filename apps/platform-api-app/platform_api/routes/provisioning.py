from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.core.config import settings
from platform_api.db.session import get_db
from platform_api.schemas.provisioning import (
    AcceptInviteRequest,
    CreateInviteRequest,
    CreateTenantRequest,
    CreateWorkspaceRequest,
)
from platform_api.services.audit_service import write_audit_log
from platform_api.services.identity_service import get_or_create_user
from platform_api.services.provisioning_service import (
    accept_invite,
    create_invite,
    create_tenant_with_owner,
    create_workspace,
)

router = APIRouter(prefix="/v1/provisioning", tags=["provisioning"])


@router.post("/tenants")
async def create_tenant(
    payload: CreateTenantRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    if not settings.allow_self_service_tenant_creation:
        raise HTTPException(
            status_code=403,
            detail="Self-service tenant creation is disabled",
        )
    user = get_or_create_user(db, principal)
    tenant = create_tenant_with_owner(db, name=payload.name, owner_user_id=user.id)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="tenant.create",
        tenant_id=tenant.id,
        details=f"name={payload.name}",
    )
    db.commit()
    return {"tenant_id": str(tenant.id), "name": tenant.name}


@router.post("/workspaces")
async def create_workspace_endpoint(
    payload: CreateWorkspaceRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    workspace = create_workspace(
        db,
        tenant_id=payload.tenant_id,
        name=payload.name,
        actor_user_id=user.id,
    )
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="workspace.create",
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        details=f"name={payload.name}",
    )
    db.commit()
    return {
        "workspace_id": str(workspace.id),
        "tenant_id": str(workspace.tenant_id),
        "name": workspace.name,
    }


@router.post("/invites")
async def create_invite_endpoint(
    payload: CreateInviteRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    invite, token = create_invite(
        db,
        tenant_id=payload.tenant_id,
        workspace_id=payload.workspace_id,
        email=str(payload.email),
        role=payload.role.value,
        expires_in_hours=payload.expires_in_hours,
        actor_user_id=user.id,
    )
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="invite.create",
        tenant_id=invite.tenant_id,
        workspace_id=invite.workspace_id,
        details=f"email={invite.email};role={invite.role}",
    )
    db.commit()
    response = {
        "invite_id": str(invite.id),
        "expires_at": invite.expires_at.isoformat(),
        "email": invite.email,
        "role": invite.role,
    }
    if settings.is_local_profile() and settings.return_invite_tokens_in_local:
        response["token"] = token
    return response


@router.post("/invites/accept")
async def accept_invite_endpoint(
    payload: AcceptInviteRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    invite = accept_invite(db, token=payload.token, user=user)
    write_audit_log(
        db,
        actor_user_id=user.id,
        action="invite.accept",
        tenant_id=invite.tenant_id,
        workspace_id=invite.workspace_id,
        details=f"invite_id={invite.id}",
    )
    db.commit()
    return {
        "invite_id": str(invite.id),
        "status": invite.status.value,
        "tenant_id": str(invite.tenant_id),
        "workspace_id": str(invite.workspace_id) if invite.workspace_id else None,
    }
