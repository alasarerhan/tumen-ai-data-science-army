"""Unit tests for M6 RBAC policy matrix.

Covers:
  - policy.py helpers for all roles
  - require_workspace_member: grants member/admin/owner, denies non-member
  - require_workspace_admin: grants admin/owner, denies member, denies non-member
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from platform_api.authz.policy import (
    can_admin_tenant,
    can_admin_workspace,
    is_tenant_member,
    is_workspace_member,
)
from platform_api.db.models import TenantRole, WorkspaceRole

# ── policy.py helpers ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", [TenantRole.owner, TenantRole.admin])
def test_can_admin_tenant_true(role):
    assert can_admin_tenant(role) is True


def test_can_admin_tenant_member_false():
    assert can_admin_tenant(TenantRole.member) is False


@pytest.mark.parametrize("role", [TenantRole.owner, TenantRole.admin, TenantRole.member])
def test_is_tenant_member_true(role):
    assert is_tenant_member(role) is True


@pytest.mark.parametrize("role", [WorkspaceRole.owner, WorkspaceRole.admin])
def test_can_admin_workspace_true(role):
    assert can_admin_workspace(role) is True


def test_can_admin_workspace_member_false():
    assert can_admin_workspace(WorkspaceRole.member) is False


@pytest.mark.parametrize("role", [WorkspaceRole.owner, WorkspaceRole.admin, WorkspaceRole.member])
def test_is_workspace_member_true(role):
    assert is_workspace_member(role) is True


# ── dependency helpers ────────────────────────────────────────────────────────


def _make_workspace():
    ws = MagicMock()
    ws.id = uuid.uuid4()
    ws.tenant_id = uuid.uuid4()
    return ws


def _make_user():
    u = MagicMock()
    u.id = uuid.uuid4()
    return u


def _make_membership(role: WorkspaceRole = WorkspaceRole.member):
    m = MagicMock()
    m.role = role
    return m


def _patched_deps(workspace=None, membership=None, user=None):
    """Return patch context managers targeting _get_workspace_and_membership."""
    ws = workspace or _make_workspace()
    u = user or _make_user()
    ctx = {"user": u, "workspace": ws, "membership": membership or _make_membership()}
    return ctx, ws, u


# ── require_workspace_member ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_workspace_member_grants_member():
    from platform_api.authz.dependencies import require_workspace_member

    ws = _make_workspace()
    u = _make_user()
    membership = _make_membership(WorkspaceRole.member)

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        return_value={"user": u, "workspace": ws, "membership": membership},
    ):
        result = await require_workspace_member(
            workspace_id=str(ws.id),
            principal=MagicMock(),
            db=MagicMock(),
        )

    assert result["workspace"] is ws
    assert result["user"] is u
    assert result["membership"] is membership


@pytest.mark.asyncio
async def test_require_workspace_member_grants_admin():
    from platform_api.authz.dependencies import require_workspace_member

    ws = _make_workspace()
    u = _make_user()
    membership = _make_membership(WorkspaceRole.admin)

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        return_value={"user": u, "workspace": ws, "membership": membership},
    ):
        result = await require_workspace_member(
            workspace_id=str(ws.id),
            principal=MagicMock(),
            db=MagicMock(),
        )

    assert result["membership"].role == WorkspaceRole.admin


@pytest.mark.asyncio
async def test_require_workspace_member_raises_403_non_member():

    ws = _make_workspace()

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        side_effect=HTTPException(status_code=403, detail="Workspace membership required"),
    ):
        from platform_api.authz.dependencies import require_workspace_member

        with pytest.raises(HTTPException) as exc_info:
            await require_workspace_member(
                workspace_id=str(ws.id),
                principal=MagicMock(),
                db=MagicMock(),
            )
        assert exc_info.value.status_code == 403


# ── require_workspace_admin ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_require_workspace_admin_grants_admin():
    from platform_api.authz.dependencies import require_workspace_admin

    ws = _make_workspace()
    u = _make_user()
    membership = _make_membership(WorkspaceRole.admin)

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        return_value={"user": u, "workspace": ws, "membership": membership},
    ):
        result = await require_workspace_admin(
            workspace_id=str(ws.id),
            principal=MagicMock(),
            db=MagicMock(),
        )

    assert result["workspace"] is ws


@pytest.mark.asyncio
async def test_require_workspace_admin_grants_owner():
    from platform_api.authz.dependencies import require_workspace_admin

    ws = _make_workspace()
    u = _make_user()
    membership = _make_membership(WorkspaceRole.owner)

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        return_value={"user": u, "workspace": ws, "membership": membership},
    ):
        result = await require_workspace_admin(
            workspace_id=str(ws.id),
            principal=MagicMock(),
            db=MagicMock(),
        )

    assert result["membership"].role == WorkspaceRole.owner


@pytest.mark.asyncio
async def test_require_workspace_admin_denies_member():
    from platform_api.authz.dependencies import require_workspace_admin

    ws = _make_workspace()
    u = _make_user()
    membership = _make_membership(WorkspaceRole.member)  # member, not admin

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        return_value={"user": u, "workspace": ws, "membership": membership},
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_workspace_admin(
                workspace_id=str(ws.id),
                principal=MagicMock(),
                db=MagicMock(),
            )

    assert exc_info.value.status_code == 403
    assert "admin" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_require_workspace_admin_raises_if_no_membership():
    from platform_api.authz.dependencies import require_workspace_admin

    ws = _make_workspace()

    with patch(
        "platform_api.authz.dependencies._get_workspace_and_membership",
        side_effect=HTTPException(status_code=403, detail="Workspace membership required"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_workspace_admin(
                workspace_id=str(ws.id),
                principal=MagicMock(),
                db=MagicMock(),
            )

    assert exc_info.value.status_code == 403
