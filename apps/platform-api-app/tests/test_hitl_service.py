from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from platform_api.db.models import HitlApprovalStatus, Workspace
from platform_api.services import hitl_service


@pytest.mark.parametrize(
    "value",
    [
        str(uuid.uuid4()),
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_parse_uuid_accepts_valid_values(value: str) -> None:
    # Act
    parsed = hitl_service._parse_uuid(value, "approval_id")

    # Assert
    assert parsed == uuid.UUID(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-uuid",
        "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130",
        "x" * 10000,
    ],
)
def test_parse_uuid_rejects_invalid_values(value: str) -> None:
    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid approval_id") as exc_info:
        hitl_service._parse_uuid(value, "approval_id")
    assert exc_info.value.status_code == 400


def test_create_hitl_approval_sets_defaults_and_payload(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id

    # Act
    item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="validate-results",
        payload={"threshold": 0.8},
        created_by_user_id=user_id,
        expires_hours=24,
    )

    # Assert
    assert item.status == HitlApprovalStatus.pending
    assert json.loads(item.payload_json) == {"threshold": 0.8}
    assert item.created_by_user_id == user_id
    assert item.expires_at is not None
    assert item.expires_at > datetime.now(UTC)


def test_list_hitl_approvals_filters_by_workspace_and_status(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    other_workspace = Workspace(tenant_id=tenant.id, name=f"other-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()

    pending_item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="pending",
        payload=None,
        created_by_user_id=user_id,
    )
    approved_item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="approved",
        payload=None,
        created_by_user_id=user_id,
    )
    approved_item.status = HitlApprovalStatus.approved
    db.add(approved_item)
    _off_scope = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=other_workspace.id,
        workflow_run_id=None,
        step_key="offscope",
        payload=None,
        created_by_user_id=user_id,
    )
    db.flush()

    # Act
    all_rows = hitl_service.list_hitl_approvals(db, workspace_id=workspace.id, status=None)
    approved_rows = hitl_service.list_hitl_approvals(
        db,
        workspace_id=workspace.id,
        status=HitlApprovalStatus.approved.value,
    )

    # Assert
    assert {row.id for row in all_rows} == {pending_item.id, approved_item.id}
    assert [row.id for row in approved_rows] == [approved_item.id]


def test_get_hitl_approval_success_and_error_paths(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    other_workspace = Workspace(tenant_id=tenant.id, name=f"isolated-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()
    item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="main",
        payload=None,
        created_by_user_id=user_id,
    )

    # Act
    fetched = hitl_service.get_hitl_approval(
        db,
        approval_id=item.id,
        workspace_id=workspace.id,
    )

    # Assert
    assert fetched.id == item.id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"not found") as not_found_exc:
        hitl_service.get_hitl_approval(
            db,
            approval_id=uuid.uuid4(),
            workspace_id=workspace.id,
        )
    assert not_found_exc.value.status_code == 404

    with pytest.raises(HTTPException, match=r"HITL approval not found") as forbidden_exc:
        hitl_service.get_hitl_approval(
            db,
            approval_id=item.id,
            workspace_id=other_workspace.id,
        )
    assert forbidden_exc.value.status_code == 404


def test_approve_hitl_transitions_pending_item(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="review",
        payload=None,
        created_by_user_id=seeded_db["user_admin"].id,
    )
    reviewer_id = seeded_db["user_member"].id

    # Act
    approved = hitl_service.approve_hitl(
        db,
        item=item,
        reviewer_user_id=reviewer_id,
        comment="looks good",
    )

    # Assert
    assert approved.status == HitlApprovalStatus.approved
    assert approved.reviewer_user_id == reviewer_id
    assert approved.comment == "looks good"
    assert approved.reviewed_at is not None


def test_approve_hitl_rejects_self_review(seeded_db: dict[str, object]) -> None:
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    creator_id = seeded_db["user_admin"].id
    item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="review",
        payload=None,
        created_by_user_id=creator_id,
    )

    with pytest.raises(HTTPException, match=r"cannot approve their own request") as exc_info:
        hitl_service.approve_hitl(
            db,
            item=item,
            reviewer_user_id=creator_id,
            comment="self review",
        )
    assert exc_info.value.status_code == 409


def test_reject_hitl_transitions_pending_item(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="review",
        payload=None,
        created_by_user_id=seeded_db["user_admin"].id,
    )
    reviewer_id = seeded_db["user_member"].id

    # Act
    rejected = hitl_service.reject_hitl(
        db,
        item=item,
        reviewer_user_id=reviewer_id,
        reason="needs correction",
    )

    # Assert
    assert rejected.status == HitlApprovalStatus.rejected
    assert rejected.reviewer_user_id == reviewer_id
    assert rejected.comment == "needs correction"
    assert rejected.reviewed_at is not None


@pytest.mark.parametrize(
    ("operation", "status"),
    [
        ("approve", HitlApprovalStatus.approved),
        ("reject", HitlApprovalStatus.rejected),
    ],
)
def test_approve_or_reject_raises_when_item_not_pending(
    seeded_db: dict[str, object],
    operation: str,
    status: HitlApprovalStatus,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    item = hitl_service.create_hitl_approval(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=None,
        step_key="final",
        payload=None,
        created_by_user_id=seeded_db["user_admin"].id,
    )
    item.status = status
    db.add(item)
    db.flush()

    # Act / Assert
    with pytest.raises(HTTPException, match=r"already in state") as exc_info:
        if operation == "approve":
            hitl_service.approve_hitl(
                db,
                item=item,
                reviewer_user_id=seeded_db["user_member"].id,
                comment=None,
            )
        else:
            hitl_service.reject_hitl(
                db,
                item=item,
                reviewer_user_id=seeded_db["user_member"].id,
                reason=None,
            )
    assert exc_info.value.status_code == 409
