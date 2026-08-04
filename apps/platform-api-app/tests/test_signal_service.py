from __future__ import annotations

import json
import uuid

import pytest
from ai_data_science_team.signals import WorkflowSignal
from fastapi import HTTPException

from platform_api.db.models import WorkflowRun, WorkflowSignalEvent, Workspace
from platform_api.services import signal_service


def _create_run(seeded_db: dict[str, object], workspace_id: uuid.UUID) -> WorkflowRun:
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


@pytest.mark.parametrize("value", [str(uuid.uuid4()), "00000000-0000-0000-0000-000000000000"])
def test_parse_uuid_accepts_valid_values(value: str) -> None:
    # Act
    parsed = signal_service._parse_uuid(value, "run_id")

    # Assert
    assert parsed == uuid.UUID(value)


@pytest.mark.parametrize(
    "value", ["", "invalid", "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130", "x" * 10000]
)
def test_parse_uuid_rejects_invalid_values(value: str) -> None:
    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid run_id") as exc_info:
        signal_service._parse_uuid(value, "run_id")
    assert exc_info.value.status_code == 400


def test_ensure_run_for_workspace_success_and_errors(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    run = _create_run(seeded_db, workspace.id)
    other_workspace = Workspace(tenant_id=tenant.id, name=f"other-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()

    # Act
    fetched = signal_service.ensure_run_for_workspace(
        db,
        run_id=str(run.id),
        workspace_id=workspace.id,
    )

    # Assert
    assert fetched.id == run.id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Workflow run not found") as not_found_exc:
        signal_service.ensure_run_for_workspace(
            db,
            run_id=str(uuid.uuid4()),
            workspace_id=workspace.id,
        )
    assert not_found_exc.value.status_code == 404

    with pytest.raises(HTTPException, match=r"Workflow run not found") as forbidden_exc:
        signal_service.ensure_run_for_workspace(
            db,
            run_id=str(run.id),
            workspace_id=other_workspace.id,
        )
    assert forbidden_exc.value.status_code == 404


@pytest.mark.parametrize("signal_type", sorted(signal_service.ALLOWED_SIGNAL_TYPES))
def test_emit_signal_accepts_all_supported_signal_types(
    seeded_db: dict[str, object],
    signal_type: str,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    run = _create_run(seeded_db, workspace.id)
    user_id = seeded_db["user_admin"].id

    # Act
    event = signal_service.emit_signal(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        signal_type=signal_type,
        target_step="step-1",
        note="test note",
        payload={"k": "v"},
        created_by_user_id=user_id,
    )

    # Assert
    assert event.signal_type == signal_type
    assert json.loads(event.payload_json) == {"k": "v"}


def test_emit_signal_rejects_unsupported_signal_type(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    run = _create_run(seeded_db, workspace.id)
    user_id = seeded_db["user_admin"].id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Unsupported signal_type") as exc_info:
        signal_service.emit_signal(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            workflow_run_id=run.id,
            signal_type="restart",
            target_step=None,
            note=None,
            payload=None,
            created_by_user_id=user_id,
        )
    assert exc_info.value.status_code == 422
    assert "annotate" in exc_info.value.detail


def test_emit_signal_mirrors_to_staged_runtime_signal_store(
    seeded_db: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    run = _create_run(seeded_db, workspace.id)
    user_id = seeded_db["user_admin"].id

    monkeypatch.setattr(signal_service.settings, "orchestration_execution_mode", "staged_m22")
    monkeypatch.setattr(
        signal_service.settings, "orchestration_state_redis_url", "redis://runtime-state"
    )

    captured: list[WorkflowSignal] = []

    class _StubSignalStore:
        def emit(self, signal: WorkflowSignal) -> WorkflowSignal:
            captured.append(signal)
            return signal

    monkeypatch.setattr(
        signal_service,
        "get_orchestration_signal_store",
        lambda: _StubSignalStore(),
    )

    signal_service.emit_signal(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        signal_type="annotate",
        target_step="feature_engineering",
        note="check outlier handling",
        payload={"priority": "high"},
        created_by_user_id=user_id,
    )

    assert len(captured) == 1
    assert captured[0].type.value == "annotate"
    assert captured[0].step_id == "feature_engineering"
    assert captured[0].payload["priority"] == "high"
    assert captured[0].payload["note"] == "check outlier handling"


def test_list_signals_orders_and_since_id_filter(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    run = _create_run(seeded_db, workspace.id)
    user_id = seeded_db["user_admin"].id
    first = signal_service.emit_signal(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        signal_type="pause",
        target_step=None,
        note="first",
        payload={"n": 1},
        created_by_user_id=user_id,
    )
    second = signal_service.emit_signal(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        signal_type="resume",
        target_step=None,
        note="second",
        payload={"n": 2},
        created_by_user_id=user_id,
    )

    # Act
    all_rows = signal_service.list_signals(db, workflow_run_id=run.id, since_id=None)
    filtered_rows = signal_service.list_signals(
        db,
        workflow_run_id=run.id,
        since_id=str(first.id),
    )

    # Assert
    assert [row.id for row in all_rows] == [first.id, second.id]
    assert first.id not in [row.id for row in filtered_rows]
    assert second.id in [row.id for row in filtered_rows]


def test_list_signals_rejects_invalid_since_id(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    run = _create_run(seeded_db, seeded_db["workspace"].id)

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid since_id") as exc_info:
        signal_service.list_signals(
            db,
            workflow_run_id=run.id,
            since_id="bad-id",
        )
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("payload_json", "expected_payload"),
    [
        (None, {}),
        ('{"a":1}', {"a": 1}),
        ("{invalid-json}", {}),
    ],
)
def test_signal_to_dict_handles_payload_variants(
    seeded_db: dict[str, object],
    payload_json: str | None,
    expected_payload: dict,
) -> None:
    # Arrange
    event = WorkflowSignalEvent(
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        workflow_run_id=uuid.uuid4(),
        signal_type="annotate",
        target_step="s1",
        note="note",
        payload_json=payload_json,
        created_by_user_id=seeded_db["user_admin"].id,
    )

    # Act
    payload = signal_service.signal_to_dict(event)

    # Assert
    assert payload["signal_type"] == "annotate"
    assert payload["payload"] == expected_payload
    assert payload["created_by_user_id"] == str(seeded_db["user_admin"].id)
    assert payload["created_at"] is not None
