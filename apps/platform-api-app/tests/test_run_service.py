from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from platform_api.db.models import User, Workspace
from platform_api.services import run_service


@pytest.mark.parametrize(
    "value",
    [
        str(uuid.uuid4()),
        "00000000-0000-0000-0000-000000000000",
        uuid.uuid4().hex,
    ],
)
def test_parse_uuid_accepts_valid_string_forms(value: str) -> None:
    # Act
    parsed = run_service._parse_uuid(value, "workspace_id")

    # Assert
    assert isinstance(parsed, uuid.UUID)
    assert str(parsed) == str(uuid.UUID(value))


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "not-a-uuid",
        "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130",
        "\U0001F600",
        "x" * 10000,
    ],
)
def test_parse_uuid_returns_http_400_for_invalid_strings(value: str) -> None:
    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid workspace_id") as exc_info:
        run_service._parse_uuid(value, "workspace_id")
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("value", "expected_exception"),
    [
        (None, TypeError),
        ([], AttributeError),
        ({}, AttributeError),
        (set(), AttributeError),
        (tuple(), AttributeError),
        (0, AttributeError),
        (-1, AttributeError),
        (float("inf"), AttributeError),
        (float("-inf"), AttributeError),
        (float("nan"), AttributeError),
        (sys.maxsize, AttributeError),
        (10**100, AttributeError),
    ],
)
def test_parse_uuid_non_string_edge_values_propagate_type_errors(
    value: object,
    expected_exception: type[Exception],
) -> None:
    # Act / Assert
    with pytest.raises(expected_exception):
        run_service._parse_uuid(value, "workspace_id")


def test_ensure_workspace_member_returns_workspace_uuid_for_member(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace_id = str(seeded_db["workspace"].id)
    user_id = seeded_db["user_admin"].id

    # Act
    result = run_service.ensure_workspace_member(db, workspace_id=workspace_id, user_id=user_id)

    # Assert
    assert result == seeded_db["workspace"].id


def test_ensure_workspace_member_raises_404_for_unknown_workspace(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    user_id = seeded_db["user_admin"].id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Workspace not found") as exc_info:
        run_service.ensure_workspace_member(db, workspace_id=str(uuid.uuid4()), user_id=user_id)
    assert exc_info.value.status_code == 404


def test_ensure_workspace_member_raises_403_when_membership_missing(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace_id = str(seeded_db["workspace"].id)
    stranger = User(sub=f"sub|{uuid.uuid4()}", email="stranger@test.local")
    db.add(stranger)
    db.flush()

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Workspace membership required") as exc_info:
        run_service.ensure_workspace_member(db, workspace_id=workspace_id, user_id=stranger.id)
    assert exc_info.value.status_code == 403


def test_get_workspace_for_member_returns_workspace_record(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_member"].id

    # Act
    result = run_service.get_workspace_for_member(
        db,
        workspace_id=str(workspace.id),
        user_id=user_id,
    )

    # Assert
    assert result.id == workspace.id
    assert result.tenant_id == workspace.tenant_id


@pytest.mark.parametrize(
    "parameters",
    [
        {},
        {"threshold": 0.5, "active": True},
        {
            "unicode": "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130 \U0001F600",
            "huge": 10**100,
            "nested": {"items": [1]},
        },
    ],
)
def test_create_workflow_run_record_persists_expected_fields(
    seeded_db: dict[str, object],
    parameters: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant_id = seeded_db["tenant"].id
    workspace_id = seeded_db["workspace"].id
    user_id = seeded_db["user_admin"].id

    # Act
    record = run_service.create_workflow_run_record(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:8]}",
        parameters=parameters,
    )

    # Assert
    assert record.status == "SCHEDULED"
    assert record.tenant_id == tenant_id
    assert record.workspace_id == workspace_id
    assert record.requested_by_user_id == user_id
    assert json.loads(record.parameters_json) == parameters


@pytest.mark.parametrize(
    ("start_time", "end_time", "expected_start", "expected_end"),
    [
        (
            "2026-03-30T10:15:30Z",
            "2026-03-30T11:15:30Z",
            datetime(2026, 3, 30, 10, 15, 30, tzinfo=UTC),
            datetime(2026, 3, 30, 11, 15, 30, tzinfo=UTC),
        ),
        (
            datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            None,
            datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            None,
        ),
        (
            None,
            None,
            None,
            None,
        ),
    ],
)
def test_update_workflow_run_status_parses_time_values_and_updates_record(
    seeded_db: dict[str, object],
    start_time: str | datetime | None,
    end_time: str | datetime | None,
    expected_start: datetime | None,
    expected_end: datetime | None,
) -> None:
    # Arrange
    db = seeded_db["db"]
    run = run_service.create_workflow_run_record(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:10]}",
        parameters={},
    )

    # Act
    updated = run_service.update_workflow_run_status(
        db,
        prefect_flow_run_id=run.prefect_flow_run_id,
        status_name="COMPLETED",
        start_time=start_time,
        end_time=end_time,
    )

    # Assert
    assert updated is not None
    assert updated.status == "COMPLETED"
    assert updated.started_at == expected_start
    assert updated.finished_at == expected_end
    assert updated.updated_at is not None


def test_update_workflow_run_status_keeps_existing_status_when_none_is_passed(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    run = run_service.create_workflow_run_record(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:10]}",
        parameters={},
    )

    # Act
    updated = run_service.update_workflow_run_status(
        db,
        prefect_flow_run_id=run.prefect_flow_run_id,
        status_name=None,
        start_time=None,
        end_time=None,
    )

    # Assert
    assert updated is not None
    assert updated.status == "SCHEDULED"


def test_update_workflow_run_status_returns_none_when_run_is_missing(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]

    # Act
    updated = run_service.update_workflow_run_status(
        db,
        prefect_flow_run_id="missing-run",
        status_name="FAILED",
        start_time=None,
        end_time=None,
    )

    # Assert
    assert updated is None


def test_update_workflow_run_status_raises_for_invalid_iso_timestamp(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    run = run_service.create_workflow_run_record(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:10]}",
        parameters={},
    )

    # Act / Assert
    with pytest.raises(ValueError):
        run_service.update_workflow_run_status(
            db,
            prefect_flow_run_id=run.prefect_flow_run_id,
            status_name="FAILED",
            start_time="not-a-timestamp",
            end_time=None,
        )


def test_get_run_by_id_for_workspace_returns_run_when_workspace_matches(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    run = run_service.create_workflow_run_record(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:10]}",
        parameters={},
    )

    # Act
    fetched = run_service.get_run_by_id_for_workspace(
        db,
        run_id=str(run.id),
        workspace_id=seeded_db["workspace"].id,
    )

    # Assert
    assert fetched.id == run.id


@pytest.mark.parametrize(
    ("run_id", "workspace_id", "status_code", "detail_pattern"),
    [
        ("not-a-uuid", str(uuid.uuid4()), 400, r"Invalid run_id"),
        (str(uuid.uuid4()), str(uuid.uuid4()), 404, r"Workflow run not found"),
    ],
)
def test_get_run_by_id_for_workspace_error_cases(
    seeded_db: dict[str, object],
    run_id: str,
    workspace_id: str,
    status_code: int,
    detail_pattern: str,
) -> None:
    # Arrange
    db = seeded_db["db"]

    # Act / Assert
    with pytest.raises(HTTPException, match=detail_pattern) as exc_info:
        run_service.get_run_by_id_for_workspace(
            db,
            run_id=run_id,
            workspace_id=uuid.UUID(workspace_id) if status_code == 404 else seeded_db["workspace"].id,
        )
    assert exc_info.value.status_code == status_code


def test_get_run_by_id_for_workspace_raises_404_for_other_workspace(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    run = run_service.create_workflow_run_record(
        db,
        tenant_id=tenant.id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:10]}",
        parameters={},
    )
    other_workspace = Workspace(tenant_id=tenant.id, name=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other_workspace)
    db.flush()

    # Act / Assert
    # Security: Returns 404 (not 403) to avoid leaking information about resource existence
    with pytest.raises(HTTPException, match=r"not found") as exc_info:
        run_service.get_run_by_id_for_workspace(
            db,
            run_id=str(run.id),
            workspace_id=other_workspace.id,
        )
    assert exc_info.value.status_code == 404


def test_list_workflow_runs_for_workspace_returns_descending_created_at(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    other_workspace = Workspace(tenant_id=tenant.id, name=f"external-{uuid.uuid4().hex[:8]}")
    db.add(other_workspace)
    db.flush()

    first = run_service.create_workflow_run_record(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:8]}",
        parameters={},
    )
    second = run_service.create_workflow_run_record(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:8]}",
        parameters={},
    )
    _off_scope = run_service.create_workflow_run_record(
        db,
        tenant_id=tenant.id,
        workspace_id=other_workspace.id,
        user_id=user_id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:8]}",
        parameters={},
    )
    first.created_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 30, 9, 0, tzinfo=UTC)
    db.add_all([first, second])
    db.flush()

    # Act
    records = run_service.list_workflow_runs_for_workspace(db, workspace_id=workspace.id)

    # Assert
    assert len(records) == 2
    assert records[0].id == second.id
    assert records[-1].id == first.id
