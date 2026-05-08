from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from platform_api.db.models import Invite, InviteStatus, TenantMembership, TenantRole, User, WorkspaceMembership, WorkspaceRole
from platform_api.services import provisioning_service


def _create_user(db, email: str | None = None) -> User:
    user = User(sub=f"sub|{uuid.uuid4()}", email=email)
    db.add(user)
    db.flush()
    return user


def test_hash_token_matches_sha256_digest() -> None:
    # Arrange
    token = "my-token"

    # Act
    hashed = provisioning_service._hash_token(token)

    # Assert
    assert hashed == hashlib.sha256(token.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("value", [str(uuid.uuid4()), "00000000-0000-0000-0000-000000000000"])
def test_parse_uuid_accepts_valid_values(value: str) -> None:
    # Act
    parsed = provisioning_service._parse_uuid(value, "tenant_id")

    # Assert
    assert parsed == uuid.UUID(value)


@pytest.mark.parametrize("value", ["", "bad-uuid", "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130", "x" * 10000])
def test_parse_uuid_rejects_invalid_values(value: str) -> None:
    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid tenant_id") as exc_info:
        provisioning_service._parse_uuid(value, "tenant_id")
    assert exc_info.value.status_code == 400


def test_get_tenant_membership_and_require_tenant_admin(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    admin_user = _create_user(db, "admin@tenant.test")
    member_user = _create_user(db, "member@tenant.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=admin_user.id, role=TenantRole.admin))
    db.add(TenantMembership(tenant_id=tenant.id, user_id=member_user.id, role=TenantRole.member))
    db.flush()

    # Act
    admin_membership = provisioning_service._get_tenant_membership(
        db,
        tenant_id=tenant.id,
        user_id=admin_user.id,
    )

    # Assert
    assert admin_membership is not None
    assert admin_membership.role == TenantRole.admin

    # Act / Assert
    provisioning_service.require_tenant_admin(
        db,
        tenant_id=tenant.id,
        user_id=admin_user.id,
    )
    with pytest.raises(HTTPException, match=r"Tenant admin/owner role required") as exc_info:
        provisioning_service.require_tenant_admin(
            db,
            tenant_id=tenant.id,
            user_id=member_user.id,
        )
    assert exc_info.value.status_code == 403


def test_create_tenant_with_owner_creates_membership(db_session) -> None:
    # Arrange
    owner = _create_user(db_session, "owner@test.local")

    # Act
    tenant = provisioning_service.create_tenant_with_owner(
        db_session,
        name="New Tenant",
        owner_user_id=owner.id,
    )

    # Assert
    membership = db_session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == owner.id,
        )
    ).scalar_one_or_none()
    assert membership is not None
    assert membership.role == TenantRole.owner


def test_create_workspace_requires_admin_and_adds_owner_membership(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    actor = _create_user(db, "actor@test.local")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.admin))
    db.flush()

    # Act
    workspace = provisioning_service.create_workspace(
        db,
        tenant_id=str(tenant.id),
        name="analytics",
        actor_user_id=actor.id,
    )

    # Assert
    owner_membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == actor.id,
        )
    ).scalar_one_or_none()
    assert owner_membership is not None
    assert owner_membership.role == WorkspaceRole.owner


def test_create_workspace_rejects_non_admin_actor(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    actor = _create_user(db, "viewer@test.local")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.member))
    db.flush()

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Tenant admin/owner role required") as exc_info:
        provisioning_service.create_workspace(
            db,
            tenant_id=str(tenant.id),
            name="forbidden",
            actor_user_id=actor.id,
        )
    assert exc_info.value.status_code == 403


def test_create_invite_generates_raw_token_and_hashed_storage(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    actor = _create_user(db, "actor@invite.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.owner))
    db.flush()

    # Act
    invite, raw_token = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email="target@test.local",
        role=WorkspaceRole.member.value,
        expires_in_hours=24,
        actor_user_id=actor.id,
    )

    # Assert
    assert raw_token
    assert invite.token_hash == provisioning_service._hash_token(raw_token)
    assert invite.status == InviteStatus.pending
    assert invite.workspace_id == workspace.id
    assert invite.email == "target@test.local"


def test_create_invite_rejects_owner_invites_from_non_owner_admin(seeded_db: dict[str, object]) -> None:
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    actor = _create_user(db, "admin-owner-invite@test.local")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.admin))
    db.flush()

    with pytest.raises(HTTPException, match=r"Only tenant owners may issue owner invites") as exc_info:
        provisioning_service.create_invite(
            db,
            tenant_id=str(tenant.id),
            workspace_id=None,
            email="target@test.local",
            role=TenantRole.owner.value,
            expires_in_hours=24,
            actor_user_id=actor.id,
        )
    assert exc_info.value.status_code == 403


def test_create_invite_expires_previous_pending_invites_for_same_scope(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    actor = _create_user(db, "actor@invite.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.owner))
    db.flush()

    first_invite, _ = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email="Target@Test.Local",
        role=WorkspaceRole.member.value,
        expires_in_hours=24,
        actor_user_id=actor.id,
    )

    # Act
    second_invite, _ = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email="target@test.local",
        role=WorkspaceRole.member.value,
        expires_in_hours=24,
        actor_user_id=actor.id,
    )

    # Assert
    assert first_invite.status == InviteStatus.expired
    assert second_invite.status == InviteStatus.pending


def test_create_invite_rejects_workspace_outside_tenant(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    actor = _create_user(db, "admin@invite.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.admin))
    db.flush()

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Workspace does not belong to tenant") as exc_info:
        provisioning_service.create_invite(
            db,
            tenant_id=str(tenant.id),
            workspace_id=str(uuid.uuid4()),
            email="target@test.local",
            role=TenantRole.member.value,
            expires_in_hours=12,
            actor_user_id=actor.id,
        )
    assert exc_info.value.status_code == 400


def test_accept_invite_success_assigns_memberships(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    actor = _create_user(db, "actor@accept.test")
    invited_user = _create_user(db, "invited@accept.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.owner))
    db.flush()
    invite, raw_token = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email=invited_user.email,
        role=WorkspaceRole.admin.value,
        expires_in_hours=48,
        actor_user_id=actor.id,
    )

    # Act
    accepted = provisioning_service.accept_invite(db, token=raw_token, user=invited_user)

    # Assert
    assert accepted.id == invite.id
    assert accepted.status == InviteStatus.accepted
    assert accepted.accepted_at is not None
    tenant_membership = db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == invited_user.id,
        )
    ).scalar_one_or_none()
    workspace_membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == invited_user.id,
        )
    ).scalar_one_or_none()
    assert tenant_membership is not None
    assert tenant_membership.role == TenantRole.admin
    assert workspace_membership is not None
    assert workspace_membership.role == WorkspaceRole.admin


@pytest.mark.parametrize(
    ("invite_role", "expected_tenant_role", "expected_workspace_role"),
    [
        ("random-role", TenantRole.member, WorkspaceRole.member),
        (TenantRole.owner.value, TenantRole.owner, WorkspaceRole.owner),
        (WorkspaceRole.member.value, TenantRole.member, WorkspaceRole.member),
    ],
)
def test_accept_invite_role_fallback_logic(
    seeded_db: dict[str, object],
    invite_role: str,
    expected_tenant_role: TenantRole,
    expected_workspace_role: WorkspaceRole,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    actor = _create_user(db, f"actor-{uuid.uuid4().hex[:4]}@fallback.test")
    invited_user = _create_user(db, f"user-{uuid.uuid4().hex[:4]}@fallback.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.owner))
    db.flush()
    invite, raw_token = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email=invited_user.email,
        role=invite_role,
        expires_in_hours=6,
        actor_user_id=actor.id,
    )

    # Act
    accepted = provisioning_service.accept_invite(db, token=raw_token, user=invited_user)

    # Assert
    assert accepted.status == InviteStatus.accepted
    tenant_membership = db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == invited_user.id,
        )
    ).scalar_one()
    workspace_membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == invited_user.id,
        )
    ).scalar_one()
    assert tenant_membership.role == expected_tenant_role
    assert workspace_membership.role == expected_workspace_role


def test_accept_invite_rejects_not_found_or_missing_email_or_not_pending_or_email_mismatch_or_expired(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    actor = _create_user(db, "actor@errors.test")
    invited_user = _create_user(db, "invited@errors.test")
    other_user = _create_user(db, "other@errors.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.owner))
    db.flush()

    # Act / Assert - not found
    with pytest.raises(HTTPException, match=r"Invite not found") as not_found_exc:
        provisioning_service.accept_invite(db, token="missing-token", user=invited_user)
    assert not_found_exc.value.status_code == 404

    # Arrange - create pending invite
    invite, raw_token = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email=invited_user.email,
        role=TenantRole.member.value,
        expires_in_hours=1,
        actor_user_id=actor.id,
    )

    # Act / Assert - missing verified email binding
    emailless_user = _create_user(db, None)
    with pytest.raises(HTTPException, match=r"verified email") as missing_email_exc:
        provisioning_service.accept_invite(db, token=raw_token, user=emailless_user)
    assert missing_email_exc.value.status_code == 403

    # Act / Assert - email mismatch
    with pytest.raises(HTTPException, match=r"email does not match") as mismatch_exc:
        provisioning_service.accept_invite(db, token=raw_token, user=other_user)
    assert mismatch_exc.value.status_code == 403

    # Arrange - mark accepted already
    invite.status = InviteStatus.accepted
    db.add(invite)
    db.flush()

    # Act / Assert - not pending
    with pytest.raises(HTTPException, match=r"Invite is not pending") as not_pending_exc:
        provisioning_service.accept_invite(db, token=raw_token, user=invited_user)
    assert not_pending_exc.value.status_code == 400

    # Arrange - expired invite
    expired_invite, expired_token = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email=invited_user.email,
        role=TenantRole.member.value,
        expires_in_hours=1,
        actor_user_id=actor.id,
    )
    expired_invite.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.add(expired_invite)
    db.flush()

    # Act / Assert - expired
    with pytest.raises(HTTPException, match=r"Invite expired") as expired_exc:
        provisioning_service.accept_invite(db, token=expired_token, user=invited_user)
    assert expired_exc.value.status_code == 400
    assert expired_invite.status == InviteStatus.expired


def test_accept_invite_preserves_existing_memberships_without_duplicates(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    actor = _create_user(db, "actor@dup.test")
    invited_user = _create_user(db, "invited@dup.test")
    db.add(TenantMembership(tenant_id=tenant.id, user_id=actor.id, role=TenantRole.owner))
    db.add(TenantMembership(tenant_id=tenant.id, user_id=invited_user.id, role=TenantRole.member))
    db.add(WorkspaceMembership(workspace_id=workspace.id, user_id=invited_user.id, role=WorkspaceRole.member))
    db.flush()
    invite, raw_token = provisioning_service.create_invite(
        db,
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        email=invited_user.email,
        role=WorkspaceRole.member.value,
        expires_in_hours=24,
        actor_user_id=actor.id,
    )

    # Act
    accepted = provisioning_service.accept_invite(db, token=raw_token, user=invited_user)

    # Assert
    assert accepted.status == InviteStatus.accepted
    tenant_rows = list(
        db.execute(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.user_id == invited_user.id,
            )
        ).scalars()
    )
    workspace_rows = list(
        db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == invited_user.id,
            )
        ).scalars()
    )
    assert len(tenant_rows) == 1
    assert len(workspace_rows) == 1
