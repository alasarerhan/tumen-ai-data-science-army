from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.authz.policy import can_admin_tenant, can_admin_workspace
from platform_api.core.service_errors import ForbiddenError
from platform_api.db.models import TenantMembership, Workspace, WorkspaceMembership, User
from platform_api.control_plane.schemas import PlatformResourceDescriptor


@dataclass(frozen=True)
class ControlPlaneContext:
    db: Session
    user: User
    workspace: Workspace
    membership: WorkspaceMembership


class PolicyEngine:
    def can_access_descriptor(
        self,
        ctx: ControlPlaneContext,
        descriptor: PlatformResourceDescriptor,
    ) -> bool:
        if descriptor.required_role == "member":
            return True
        if descriptor.required_role == "workspace_admin":
            return can_admin_workspace(ctx.membership.role)
        if descriptor.required_role == "tenant_admin":
            membership = ctx.db.execute(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == ctx.workspace.tenant_id,
                    TenantMembership.user_id == ctx.user.id,
                )
            ).scalar_one_or_none()
            return bool(membership and can_admin_tenant(membership.role))
        return False

    def require_descriptor_access(
        self,
        ctx: ControlPlaneContext,
        descriptor: PlatformResourceDescriptor,
    ) -> None:
        if not self.can_access_descriptor(ctx, descriptor):
            raise ForbiddenError(f"{descriptor.label} requires {descriptor.required_role} access")

    def redact_record(
        self,
        record: dict[str, Any],
        descriptor: PlatformResourceDescriptor,
    ) -> dict[str, Any]:
        redacted = dict(record)
        for field in descriptor.redacted_fields:
            self._redact_path(redacted, field)
        return redacted

    def _redact_path(self, record: dict[str, Any], dotted_path: str) -> None:
        parts = dotted_path.split(".")
        target: dict[str, Any] = record
        for part in parts[:-1]:
            value = target.get(part)
            if not isinstance(value, dict):
                return
            target = value
        leaf = parts[-1]
        if leaf in target:
            target[leaf] = "<redacted>"


policy_engine = PolicyEngine()
