from __future__ import annotations

import uuid

import pytest

from platform_api.services.audit_service import write_audit_log


@pytest.mark.parametrize(
    ("action", "details"),
    [
        ("invite.created", None),
        ("workspace.updated", '{"field":"name"}'),
        ("unicode.event", "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130 \U0001f4ca"),
    ],
)
def test_write_audit_log_persists_record(
    db_session,
    action: str,
    details: str | None,
) -> None:
    # Arrange
    actor_user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # Act
    record = write_audit_log(
        db_session,
        actor_user_id=actor_user_id,
        action=action,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        details=details,
    )

    # Assert
    assert record.id is not None
    assert record.actor_user_id == actor_user_id
    assert record.action == action
    assert record.tenant_id == tenant_id
    assert record.workspace_id == workspace_id
    assert record.details == details
