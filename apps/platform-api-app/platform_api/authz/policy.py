"""RBAC Policy Matrix — single source of truth.

Endpoint-level permission requirements
=======================================

Tenant-scoped
  POST /v1/provisioning/tenants          any authenticated user
  POST /v1/provisioning/workspaces       tenant admin | tenant owner
  POST /v1/provisioning/invites          tenant admin | tenant owner
  POST /v1/provisioning/invites/accept   any authenticated user

Workspace-scoped (member = any of owner/admin/member)
  GET  /v1/runs                          workspace member
  GET  /v1/artifacts                     workspace member
  POST /v1/artifacts                     workspace member
  GET  /v1/artifacts/{id}/access         workspace member
  GET  /v1/workflows                     workspace member
  POST /v1/workflows                     workspace member
  GET  /v1/workflows/latest              workspace member
  GET  /v1/workflows/{id}                workspace member
  POST /v1/workflows/{id}/publish        workspace admin | workspace owner
  POST /v1/workflows/{id}/archive        workspace admin | workspace owner
  GET  /v1/strategy/reports/generate     workspace member
"""

from __future__ import annotations

from platform_api.db.models import TenantRole, WorkspaceRole

# ---------------------------------------------------------------------------
# Tenant-level helpers
# ---------------------------------------------------------------------------


def can_admin_tenant(role: TenantRole) -> bool:
    """True if *role* may administer a tenant (create workspaces, send invites)."""
    return role in {TenantRole.owner, TenantRole.admin}


def is_tenant_member(role: TenantRole) -> bool:
    """True for any valid tenant membership."""
    return role in {TenantRole.owner, TenantRole.admin, TenantRole.member}


# ---------------------------------------------------------------------------
# Workspace-level helpers
# ---------------------------------------------------------------------------


def can_admin_workspace(role: WorkspaceRole) -> bool:
    """True if *role* may perform admin actions (publish/archive specs, etc.)."""
    return role in {WorkspaceRole.owner, WorkspaceRole.admin}


def is_workspace_member(role: WorkspaceRole) -> bool:
    """True for any valid workspace membership (read / run access)."""
    return role in {WorkspaceRole.owner, WorkspaceRole.admin, WorkspaceRole.member}
