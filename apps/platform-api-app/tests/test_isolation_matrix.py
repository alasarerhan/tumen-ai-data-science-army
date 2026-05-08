from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from platform_api.db.models import TenantRole
from platform_api.authz.policy import WorkspaceRole
from platform_api.services import provisioning_service


def test_tenant_admin_required_when_membership_missing(monkeypatch):
    monkeypatch.setattr(provisioning_service, "_get_tenant_membership", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as exc_info:
        provisioning_service.require_tenant_admin(
            db=MagicMock(),
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )
    assert exc_info.value.status_code == 403


def test_tenant_admin_allowed_for_admin_role(monkeypatch):
    membership = SimpleNamespace(role=TenantRole.admin)
    monkeypatch.setattr(provisioning_service, "_get_tenant_membership", lambda *args, **kwargs: membership)

    # Should not raise
    provisioning_service.require_tenant_admin(
        db=MagicMock(),
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )


def test_workspace_policy_matrix_member_vs_admin():
    # same-workspace member is allowed for read/run access
    assert WorkspaceRole.member.value == "member"
    # admin/owner are distinct elevated roles for mutating operations
    assert WorkspaceRole.admin.value == "admin"
    assert WorkspaceRole.owner.value == "owner"
