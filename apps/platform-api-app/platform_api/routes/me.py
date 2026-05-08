from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.services.identity_service import (
    get_or_create_user,
    list_tenant_memberships,
    list_workspace_memberships,
)

router = APIRouter(prefix="/v1")


@router.get("/me")
async def me(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    tenant_memberships = list_tenant_memberships(db, user.id)
    workspace_memberships = list_workspace_memberships(db, user.id)
    db.commit()

    return {
        "id": str(user.id),
        "sub": user.sub,
        "email": user.email,
        "tenant_memberships": [
            {
                "tenant_id": str(membership.tenant_id),
                "role": membership.role.value,
            }
            for membership in tenant_memberships
        ],
        "workspace_memberships": [
            {
                "workspace_id": str(membership.workspace_id),
                "role": membership.role.value,
            }
            for membership in workspace_memberships
        ],
        "claims": principal.claims,
    }
