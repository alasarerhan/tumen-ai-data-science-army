from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.authz.policy import can_admin_tenant
from platform_api.core.service_errors import ForbiddenError, NotFoundError, ValidationError
from platform_api.db.models import (
    Invite,
    InviteStatus,
    Tenant,
    TenantMembership,
    TenantRole,
    User,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)
from platform_api.services.identity_service import normalize_email


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {label}") from exc


def _get_tenant_membership(
    db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> TenantMembership | None:
    return db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    ).scalar_one_or_none()


def require_tenant_admin(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    membership = _get_tenant_membership(db, tenant_id=tenant_id, user_id=user_id)
    if membership is None or not can_admin_tenant(membership.role):
        raise ForbiddenError("Tenant admin/owner role required")


def _require_invite_role_grant(
    membership: TenantMembership,
    *,
    invite_role: str,
) -> None:
    if invite_role == TenantRole.owner.value and membership.role != TenantRole.owner:
        raise ForbiddenError("Only tenant owners may issue owner invites")


def create_tenant_with_owner(db: Session, *, name: str, owner_user_id: uuid.UUID) -> Tenant:
    tenant = Tenant(name=name)
    db.add(tenant)
    db.flush()

    tenant_membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=owner_user_id,
        role=TenantRole.owner,
    )
    db.add(tenant_membership)
    db.flush()
    return tenant


def create_workspace(
    db: Session, *, tenant_id: str, name: str, actor_user_id: uuid.UUID
) -> Workspace:
    tenant_uuid = _parse_uuid(tenant_id, "tenant_id")
    require_tenant_admin(db, tenant_id=tenant_uuid, user_id=actor_user_id)

    workspace = Workspace(tenant_id=tenant_uuid, name=name)
    db.add(workspace)
    db.flush()

    existing = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == actor_user_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=actor_user_id,
                role=WorkspaceRole.owner,
            )
        )
        db.flush()

    return workspace


def create_invite(
    db: Session,
    *,
    tenant_id: str,
    workspace_id: str | None,
    email: str,
    role: str,
    expires_in_hours: int,
    actor_user_id: uuid.UUID,
) -> tuple[Invite, str]:
    tenant_uuid = _parse_uuid(tenant_id, "tenant_id")
    actor_membership = _get_tenant_membership(db, tenant_id=tenant_uuid, user_id=actor_user_id)
    if actor_membership is None or not can_admin_tenant(actor_membership.role):
        raise ForbiddenError("Tenant admin/owner role required")
    _require_invite_role_grant(actor_membership, invite_role=role)
    normalized_email = normalize_email(email)
    if normalized_email is None:
        raise ValidationError("Invite email is required")

    workspace_uuid: uuid.UUID | None = None
    if workspace_id:
        workspace_uuid = _parse_uuid(workspace_id, "workspace_id")
        workspace = db.execute(
            select(Workspace).where(Workspace.id == workspace_uuid)
        ).scalar_one_or_none()
        if workspace is None or workspace.tenant_id != tenant_uuid:
            raise ValidationError("Workspace does not belong to tenant")

    superseded_invites = list(
        db.execute(
            select(Invite).where(
                Invite.tenant_id == tenant_uuid,
                Invite.workspace_id == workspace_uuid,
                Invite.email == normalized_email,
                Invite.status == InviteStatus.pending,
            )
        ).scalars()
    )
    for existing_invite in superseded_invites:
        existing_invite.status = InviteStatus.expired
        db.add(existing_invite)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    invite = Invite(
        tenant_id=tenant_uuid,
        workspace_id=workspace_uuid,
        email=normalized_email,
        role=role,
        token_hash=token_hash,
        status=InviteStatus.pending,
        expires_at=datetime.now(UTC) + timedelta(hours=expires_in_hours),
        created_by_user_id=actor_user_id,
    )
    db.add(invite)
    db.flush()

    return invite, raw_token


def _ensure_tenant_membership(
    db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID, role: TenantRole
) -> None:
    existing = _get_tenant_membership(db, tenant_id=tenant_id, user_id=user_id)
    if existing is None:
        db.add(TenantMembership(tenant_id=tenant_id, user_id=user_id, role=role))
        db.flush()


def _ensure_workspace_membership(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceRole,
) -> None:
    existing = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(WorkspaceMembership(workspace_id=workspace_id, user_id=user_id, role=role))
        db.flush()


def accept_invite(db: Session, *, token: str, user: User) -> Invite:
    """Accept an invite by token.

    Security: The invite is looked up by token_hash, but we validate that the
    authenticated user's email matches the invite email to prevent IDOR.
    """
    token_hash = _hash_token(token)
    invite = db.execute(select(Invite).where(Invite.token_hash == token_hash)).scalar_one_or_none()
    if invite is None:
        raise NotFoundError("Invite not found")

    now = datetime.now(UTC)
    if invite.status != InviteStatus.pending:
        raise ValidationError("Invite is not pending")
    if invite.expires_at < now:
        invite.status = InviteStatus.expired
        db.add(invite)
        raise ValidationError("Invite expired")

    normalized_user_email = normalize_email(user.email)
    if normalized_user_email is None:
        raise ForbiddenError("Authenticated account must have a verified email")

    if normalized_user_email != normalize_email(invite.email):
        raise ForbiddenError("Invite email does not match authenticated user")

    role_str = invite.role
    if role_str in {TenantRole.owner.value, TenantRole.admin.value, TenantRole.member.value}:
        _ensure_tenant_membership(
            db,
            tenant_id=invite.tenant_id,
            user_id=user.id,
            role=TenantRole(role_str),
        )
    else:
        _ensure_tenant_membership(
            db,
            tenant_id=invite.tenant_id,
            user_id=user.id,
            role=TenantRole.member,
        )

    if invite.workspace_id is not None:
        workspace_role = WorkspaceRole.member
        if role_str in {
            WorkspaceRole.owner.value,
            WorkspaceRole.admin.value,
            WorkspaceRole.member.value,
        }:
            workspace_role = WorkspaceRole(role_str)
        _ensure_workspace_membership(
            db,
            workspace_id=invite.workspace_id,
            user_id=user.id,
            role=workspace_role,
        )

    invite.status = InviteStatus.accepted
    invite.accepted_at = now
    db.add(invite)
    db.flush()
    return invite
