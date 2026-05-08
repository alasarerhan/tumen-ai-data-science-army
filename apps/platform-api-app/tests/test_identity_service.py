from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from platform_api.auth.models import Principal
from platform_api.db.models import (
    TenantMembership,
    TenantRole,
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
)
from platform_api.services.identity_service import (
    get_or_create_user,
    list_tenant_memberships,
    list_workspace_memberships,
)


def test_get_or_create_user_creates_new_user(db_session: Session) -> None:
    # Arrange
    principal = Principal(sub=f"sub|{uuid.uuid4()}", email="new.user@test.local", claims={})

    # Act
    user = get_or_create_user(db_session, principal)

    # Assert
    assert user.id is not None
    assert user.sub == principal.sub
    assert user.email == principal.email


@pytest.mark.parametrize(
    ("existing_email", "principal_email", "expected_email"),
    [
        ("old@test.local", "updated@test.local", "updated@test.local"),
        ("same@test.local", "same@test.local", "same@test.local"),
        ("persist@test.local", None, "persist@test.local"),
    ],
)
def test_get_or_create_user_updates_email_only_when_new_email_is_provided(
    db_session: Session,
    existing_email: str | None,
    principal_email: str | None,
    expected_email: str | None,
) -> None:
    # Arrange
    sub = f"sub|{uuid.uuid4()}"
    existing = get_or_create_user(
        db_session,
        Principal(sub=sub, email=existing_email, claims={}),
    )
    principal = Principal(sub=sub, email=principal_email, claims={})

    # Act
    updated = get_or_create_user(db_session, principal)

    # Assert
    assert updated.id == existing.id
    assert updated.email == expected_email


def test_get_or_create_user_rejects_email_reuse_across_subjects(db_session: Session) -> None:
    # Arrange
    original = Principal(sub=f"sub|{uuid.uuid4()}", email="shared@test.local", claims={})
    challenger = Principal(sub=f"sub|{uuid.uuid4()}", email="shared@test.local", claims={})
    get_or_create_user(db_session, original)

    # Act / Assert
    with pytest.raises(HTTPException, match=r"already linked") as exc_info:
        get_or_create_user(db_session, challenger)

    assert exc_info.value.status_code == 409


def test_list_tenant_memberships_returns_only_requested_user_rows(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    user_admin = seeded_db["user_admin"]
    user_member = seeded_db["user_member"]
    tenant_membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=user_admin.id,
        role=TenantRole.admin,
    )
    other_membership = TenantMembership(
        tenant_id=tenant.id,
        user_id=user_member.id,
        role=TenantRole.member,
    )
    db.add_all([tenant_membership, other_membership])
    db.flush()

    # Act
    memberships = list_tenant_memberships(db, user_admin.id)

    # Assert
    assert len(memberships) == 1
    assert memberships[0].user_id == user_admin.id
    assert memberships[0].tenant_id == tenant.id


@pytest.mark.parametrize(
    ("user_key", "expected_count"),
    [
        ("user_admin", 2),
        ("user_member", 1),
    ],
)
def test_list_workspace_memberships_filters_by_user(
    seeded_db: dict[str, object],
    user_key: str,
    expected_count: int,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    user_admin = seeded_db["user_admin"]
    target_user = seeded_db[user_key]
    extra_workspace = Workspace(tenant_id=tenant.id, name=f"secondary-{uuid.uuid4().hex[:8]}")
    db.add(extra_workspace)
    db.flush()

    # Add a second membership for admin in another workspace.
    extra_workspace_membership = WorkspaceMembership(
        workspace_id=extra_workspace.id,
        user_id=user_admin.id,
        role=WorkspaceRole.admin,
    )
    db.add(extra_workspace_membership)
    db.flush()

    # Act
    memberships = list_workspace_memberships(db, target_user.id)

    # Assert
    assert len(memberships) == expected_count
    assert all(membership.user_id == target_user.id for membership in memberships)
