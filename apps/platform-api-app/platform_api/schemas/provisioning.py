from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from platform_api.db.models import TenantRole, WorkspaceRole


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)


class CreateWorkspaceRequest(BaseModel):
    tenant_id: str
    name: str = Field(min_length=2, max_length=200)


class CreateInviteRequest(BaseModel):
    tenant_id: str
    workspace_id: str | None = None
    email: EmailStr
    role: TenantRole | WorkspaceRole
    expires_in_hours: int = Field(default=48, ge=1, le=168)


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=16)
