from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from platform_api.db.models import User, WorkflowRun, Workspace, WorkspaceMembership, WorkspaceRole
from platform_api.services import artifact_service


@pytest.mark.parametrize(
    "value",
    [
        str(uuid.uuid4()),
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_parse_uuid_accepts_valid_values(value: str) -> None:
    # Act
    parsed = artifact_service._parse_uuid(value, "artifact_id")

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
def test_parse_uuid_raises_http_400_for_invalid_input(value: str) -> None:
    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid artifact_id") as exc_info:
        artifact_service._parse_uuid(value, "artifact_id")
    assert exc_info.value.status_code == 400


def test_authorized_workspace_returns_workspace_for_member(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_member"].id

    # Act
    authorized = artifact_service._authorized_workspace(
        db,
        workspace_id=str(workspace.id),
        user_id=user_id,
    )

    # Assert
    assert authorized.id == workspace.id


def test_authorized_workspace_raises_404_when_workspace_missing(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    user_id = seeded_db["user_member"].id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Workspace not found") as exc_info:
        artifact_service._authorized_workspace(
            db,
            workspace_id=str(uuid.uuid4()),
            user_id=user_id,
        )
    assert exc_info.value.status_code == 404


def test_authorized_workspace_raises_403_when_membership_missing(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    stranger = User(sub=f"sub|{uuid.uuid4()}", email="stranger@local.test")
    db.add(stranger)
    db.flush()

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Workspace membership required") as exc_info:
        artifact_service._authorized_workspace(
            db,
            workspace_id=str(workspace.id),
            user_id=stranger.id,
        )
    assert exc_info.value.status_code == 403


def _create_run_in_workspace(seeded_db: dict[str, object], workspace_id: uuid.UUID) -> WorkflowRun:
    db = seeded_db["db"]
    tenant_id = seeded_db["tenant"].id
    user_id = seeded_db["user_admin"].id
    run = WorkflowRun(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        requested_by_user_id=user_id,
        flow_key="hello",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex[:10]}",
        status="SCHEDULED",
        parameters_json="{}",
        started_at=None,
        finished_at=None,
    )
    db.add(run)
    db.flush()
    return run


@pytest.mark.parametrize("workflow_run_id", [None, ""])
def test_create_artifact_record_without_run_id(
    seeded_db: dict[str, object],
    workflow_run_id: str | None,
) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id

    # Act
    artifact = artifact_service.create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=workflow_run_id,
        kind="report",
        uri="s3://bucket/report.json",
        user_id=user_id,
    )

    # Assert
    assert artifact.workflow_run_id is None
    assert artifact.workspace_id == workspace.id
    assert artifact.created_by_user_id == user_id


def test_create_artifact_record_with_valid_workflow_run(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    run = _create_run_in_workspace(seeded_db, workspace.id)
    user_id = seeded_db["user_admin"].id

    # Act
    artifact = artifact_service.create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=str(run.id),
        kind="table",
        uri="memory://table",
        user_id=user_id,
    )

    # Assert
    assert artifact.workflow_run_id == run.id


def test_create_artifact_record_rejects_run_from_other_workspace(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    other_workspace = Workspace(tenant_id=tenant.id, name=f"secondary-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()
    run = _create_run_in_workspace(seeded_db, other_workspace.id)
    user_id = seeded_db["user_admin"].id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"workflow_run_id not in workspace") as exc_info:
        artifact_service.create_artifact_record(
            db,
            workspace_id=str(workspace.id),
            workflow_run_id=str(run.id),
            kind="table",
            uri="memory://table",
            user_id=user_id,
        )
    assert exc_info.value.status_code == 400


def test_list_artifacts_for_workspace_filters_and_orders(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    other_workspace = Workspace(tenant_id=tenant.id, name=f"other-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()
    user_id = seeded_db["user_admin"].id
    db.add(
        WorkspaceMembership(
            workspace_id=other_workspace.id,
            user_id=user_id,
            role=WorkspaceRole.admin,
        )
    )
    db.flush()

    first = artifact_service.create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=None,
        kind="report",
        uri="s3://bucket/first",
        user_id=user_id,
    )
    second = artifact_service.create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=None,
        kind="chart",
        uri="s3://bucket/second",
        user_id=user_id,
    )
    _off_scope = artifact_service.create_artifact_record(
        db,
        workspace_id=str(other_workspace.id),
        workflow_run_id=None,
        kind="offscope",
        uri="s3://bucket/other",
        user_id=user_id,
    )
    first.created_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 30, 9, 0, tzinfo=UTC)
    db.add_all([first, second])
    db.flush()

    # Act
    artifacts = artifact_service.list_artifacts_for_workspace(
        db,
        workspace_id=str(workspace.id),
        user_id=user_id,
    )

    # Assert
    assert len(artifacts) == 2
    assert artifacts[0].id == second.id
    assert artifacts[-1].id == first.id


def test_get_artifact_for_workspace_success_and_error_paths(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    other_workspace = Workspace(tenant_id=tenant.id, name=f"isolated-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()
    user_id = seeded_db["user_admin"].id
    db.add(
        WorkspaceMembership(
            workspace_id=other_workspace.id,
            user_id=user_id,
            role=WorkspaceRole.admin,
        )
    )
    db.flush()
    artifact = artifact_service.create_artifact_record(
        db,
        workspace_id=str(workspace.id),
        workflow_run_id=None,
        kind="report",
        uri="s3://bucket/main",
        user_id=user_id,
    )
    off_scope_artifact = artifact_service.create_artifact_record(
        db,
        workspace_id=str(other_workspace.id),
        workflow_run_id=None,
        kind="private",
        uri="s3://bucket/private",
        user_id=user_id,
    )

    # Act
    fetched = artifact_service.get_artifact_for_workspace(
        db,
        artifact_id=str(artifact.id),
        workspace_id=str(workspace.id),
        user_id=user_id,
    )

    # Assert
    assert fetched.id == artifact.id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Artifact not found") as not_found_exc:
        artifact_service.get_artifact_for_workspace(
            db,
            artifact_id=str(uuid.uuid4()),
            workspace_id=str(workspace.id),
            user_id=user_id,
        )
    assert not_found_exc.value.status_code == 404

    with pytest.raises(HTTPException, match=r"Artifact not found") as denied_exc:
        artifact_service.get_artifact_for_workspace(
            db,
            artifact_id=str(off_scope_artifact.id),
            workspace_id=str(workspace.id),
            user_id=user_id,
        )
    assert denied_exc.value.status_code == 404
