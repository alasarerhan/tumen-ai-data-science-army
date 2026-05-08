from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from platform_api.db.models import ChatMessage, ChatMessageRole, ChatSession, ChatSessionStatus, ChatUpload
from platform_api.services import chat_service
from platform_api.services.workflow_chain_validator import inspect_workflow_spec


@pytest.fixture()
def upload_dir() -> Path:
    path = Path.cwd() / ".chat_test_uploads" / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize(
    ("raw_title", "expected"),
    [
        ("Sales review", "Sales review"),
        ("   padded title   ", "padded title"),
        ("", "New chat"),
        ("   ", "New chat"),
        (None, "New chat"),
        ("x" * 300, "x" * 200),
    ],
)
def test_create_chat_session_normalizes_title(
    seeded_db: dict[str, object],
    raw_title: str | None,
    expected: str,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id

    # Act
    session = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        title=raw_title,
    )

    # Assert
    assert session.title == expected
    assert session.status == ChatSessionStatus.active


def test_list_chat_sessions_filters_by_workspace_and_user(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_admin = seeded_db["user_admin"]
    user_member = seeded_db["user_member"]

    first = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_admin.id,
        title="first",
    )
    second = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_admin.id,
        title="second",
    )
    _other_user = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_member.id,
        title="member",
    )
    first.updated_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    second.updated_at = datetime(2026, 3, 30, 9, 0, tzinfo=UTC)
    db.add_all([first, second])
    db.flush()

    # Act
    rows = chat_service.list_chat_sessions(
        db,
        workspace_id=workspace.id,
        user_id=user_admin.id,
    )

    # Assert
    assert len(rows) == 2
    assert rows[0].id == second.id
    assert rows[-1].id == first.id


def test_get_chat_session_success_and_errors(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    session = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=seeded_db["user_admin"].id,
        title="session",
    )

    # Act
    fetched = chat_service.get_chat_session(
        db,
        session_id=str(session.id),
        workspace_id=workspace.id,
    )

    # Assert
    assert fetched.id == session.id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Chat session not found") as not_found_exc:
        chat_service.get_chat_session(
            db,
            session_id=str(uuid.uuid4()),
            workspace_id=workspace.id,
        )
    assert not_found_exc.value.status_code == 404

    with pytest.raises(HTTPException, match=r"Chat session not found") as forbidden_exc:
        chat_service.get_chat_session(
            db,
            session_id=str(session.id),
            workspace_id=uuid.uuid4(),
        )
    assert forbidden_exc.value.status_code == 404


@pytest.mark.parametrize(
    ("role", "content", "artifacts"),
    [
        (ChatMessageRole.user, "hello", None),
        (ChatMessageRole.assistant, "analysis", [{"type": "report", "x": 1}]),
        (ChatMessageRole.system, "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130 \U0001F4CA", []),
    ],
)
def test_create_message_sets_session_update_and_artifacts_json(
    seeded_db: dict[str, object],
    role: ChatMessageRole,
    content: str,
    artifacts: list[dict] | None,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    session = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=seeded_db["user_admin"].id,
        title="chat",
    )
    before = session.updated_at

    # Act
    message = chat_service.create_message(
        db,
        session=session,
        role=role,
        content=content,
        artifacts=artifacts,
    )

    # Assert
    assert message.role == role
    assert message.content == content
    if artifacts:
        assert json.loads(message.artifacts_json) == artifacts
    else:
        assert message.artifacts_json is None
    assert session.updated_at is not None
    assert session.updated_at != before


def test_list_messages_returns_ascending_order(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    session = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=seeded_db["user_admin"].id,
        title="ordered",
    )
    first = chat_service.create_message(
        db,
        session=session,
        role=ChatMessageRole.user,
        content="first",
        artifacts=None,
    )
    second = chat_service.create_message(
        db,
        session=session,
        role=ChatMessageRole.assistant,
        content="second",
        artifacts=None,
    )
    first.created_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 30, 9, 0, tzinfo=UTC)
    db.add_all([first, second])
    db.flush()

    # Act
    rows = chat_service.list_messages(db, session_id=session.id)

    # Assert
    assert [row.id for row in rows] == [first.id, second.id]


def test_build_assistant_reply_returns_workflow_design_for_pipeline_requests() -> None:
    text, artifacts = chat_service.build_assistant_reply("Create a daily anomaly detection workflow")
    workflow_spec = artifacts[0]["workflow_spec"]
    validation = inspect_workflow_spec(workflow_spec)

    assert "workflow" in text.lower()
    assert artifacts[0]["type"] == "workflow_design"
    assert workflow_spec["steps"]
    assert workflow_spec["schedule"]["cron"] == "0 8 * * *"
    assert workflow_spec["steps"][0]["agent"] == "EDA"
    assert workflow_spec["steps"][1]["agent"] == "Data Cleaning"
    assert workflow_spec["steps"][2]["agent"] == "Anomaly Detection"
    assert workflow_spec["steps"][-1]["agent"] == "Narrative"
    assert validation["errors"] == []


def test_build_assistant_reply_returns_valid_forecasting_workflow_design() -> None:
    _text, artifacts = chat_service.build_assistant_reply("Create a weekly forecast workflow for revenue")
    workflow_spec = artifacts[0]["workflow_spec"]
    validation = inspect_workflow_spec(workflow_spec)

    assert [step["agent"] for step in workflow_spec["steps"][:3]] == [
        "EDA",
        "Data Cleaning",
        "Time Series EDA",
    ]
    assert workflow_spec["steps"][3]["agent"] == "Forecasting Model"
    assert workflow_spec["schedule"]["cron"] == "0 8 * * 1"
    assert validation["errors"] == []


def test_save_upload_writes_file_and_persists_metadata(
    seeded_db: dict[str, object],
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    session = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        title="upload",
    )
    monkeypatch.setattr(chat_service.settings, "chat_upload_dir", str(upload_dir))
    payload = b"file-content"

    # Act
    upload = chat_service.save_upload(
        db,
        session=session,
        filename="../unsafe-name.csv",
        content_type="text/csv",
        file_bytes=payload,
        created_by_user_id=user_id,
    )

    # Assert
    assert upload.filename == "unsafe-name.csv"
    assert upload.size_bytes == len(payload)
    stored_file = upload_dir / upload.storage_uri
    assert stored_file.exists()
    assert stored_file.read_bytes() == payload


def test_list_uploads_orders_descending_created_at(
    seeded_db: dict[str, object],
    upload_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    session = chat_service.create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        title="upload-order",
    )
    monkeypatch.setattr(chat_service.settings, "chat_upload_dir", str(upload_dir))

    first = chat_service.save_upload(
        db,
        session=session,
        filename="first.txt",
        content_type=None,
        file_bytes=b"first",
        created_by_user_id=user_id,
    )
    second = chat_service.save_upload(
        db,
        session=session,
        filename="second.txt",
        content_type=None,
        file_bytes=b"second",
        created_by_user_id=user_id,
    )
    first.created_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 30, 9, 0, tzinfo=UTC)
    db.add_all([first, second])
    db.flush()

    # Act
    rows = chat_service.list_uploads(db, session_id=session.id)

    # Assert
    assert [row.id for row in rows] == [second.id, first.id]


@pytest.mark.parametrize(
    ("prompt", "expected_types"),
    [
        ("chart and table", {"chart", "table"}),
        ("python code and summary", {"code", "report"}),
        ("nothing special", {"report"}),
        ("\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130 grafik tablo", {"chart", "table"}),
    ],
)
def test_build_assistant_reply_generates_expected_artifact_types(
    prompt: str,
    expected_types: set[str],
) -> None:
    # Act
    text, artifacts = chat_service.build_assistant_reply(prompt)

    # Assert
    assert "structured artifacts" in text.lower()
    assert expected_types.issubset({artifact["type"] for artifact in artifacts})


@pytest.mark.parametrize(
    ("artifacts_json", "expected_artifacts"),
    [
        (None, []),
        ('[{"type":"chart"}]', [{"type": "chart"}]),
        ("invalid-json", []),
    ],
)
def test_message_to_dict_handles_artifact_json_variants(
    seeded_db: dict[str, object],
    artifacts_json: str | None,
    expected_artifacts: list[dict],
) -> None:
    # Arrange
    message = ChatMessage(
        session_id=uuid.uuid4(),
        role=ChatMessageRole.assistant,
        content="hello",
        artifacts_json=artifacts_json,
    )

    # Act
    payload = chat_service.message_to_dict(message)

    # Assert
    assert payload["role"] == ChatMessageRole.assistant.value
    assert payload["artifacts"] == expected_artifacts
    assert payload["created_at"] is None


def test_session_to_dict_and_upload_to_dict_serialization(seeded_db: dict[str, object]) -> None:
    # Arrange
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    session = ChatSession(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        title="serialize",
        status=ChatSessionStatus.active,
    )
    upload = ChatUpload(
        session_id=uuid.uuid4(),
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        filename="file.csv",
        content_type="text/csv",
        size_bytes=123,
        storage_uri="file://tmp/file.csv",
        created_by_user_id=user_id,
    )

    # Act
    session_payload = chat_service.session_to_dict(session)
    upload_payload = chat_service.upload_to_dict(upload)

    # Assert
    assert session_payload["title"] == "serialize"
    assert session_payload["status"] == ChatSessionStatus.active.value
    assert upload_payload["filename"] == "file.csv"
    assert upload_payload["size_bytes"] == 123
