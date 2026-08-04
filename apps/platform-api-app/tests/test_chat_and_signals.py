"""TG1/TG2 tests for chat and workflow signal APIs (M21 + M17 UI backend support)."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import pytest
from ai_data_science_team.signals import WorkflowSignal
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.main import create_app
from platform_api.services.chat_service import ChatStreamEvent


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def admin_client(app, seeded_db):
    user = seeded_db["user_admin"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal():
        return principal

    def _db():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db
    app.dependency_overrides.clear()


class TestChatSessionLifecycle:
    def test_create_and_list_session(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)

        created = client.post(
            "/v1/chat/sessions", json={"workspace_id": ws_id, "title": "Revenue Chat"}
        )
        assert created.status_code == 201
        body = created.json()
        assert body["title"] == "Revenue Chat"

        listed = client.get(f"/v1/chat/sessions?workspace_id={ws_id}")
        assert listed.status_code == 200
        assert len(listed.json()["items"]) >= 1

    def test_message_create_returns_artifacts(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)

        created = client.post(
            "/v1/chat/sessions", json={"workspace_id": ws_id, "title": "Artifacts"}
        ).json()
        sid = created["id"]

        msg = client.post(
            f"/v1/chat/sessions/{sid}/messages",
            json={"workspace_id": ws_id, "content": "Please generate chart and table summary"},
        )
        assert msg.status_code == 201
        payload = msg.json()
        assert payload["role"] == "assistant"
        assert isinstance(payload["artifacts"], list)
        assert len(payload["artifacts"]) >= 1

    def test_stream_endpoint_emits_done(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        sid = client.post("/v1/chat/sessions", json={"workspace_id": ws_id, "title": "SSE"}).json()[
            "id"
        ]

        async def fake_stream(*args, **kwargs):
            yield ChatStreamEvent(type="progress")
            yield ChatStreamEvent(
                type="final",
                delta="streamed assistant text",
                text="streamed assistant text",
                artifacts=[
                    {"type": "report", "title": "Done", "content": "streamed assistant text"}
                ],
            )

        with patch("platform_api.routes.chat.stream_assistant_reply", fake_stream):
            with client.stream(
                "POST",
                f"/v1/chat/sessions/{sid}/messages/stream",
                json={"workspace_id": ws_id, "content": "stream response please"},
            ) as response:
                assert response.status_code == 200
                lines = [line for line in response.iter_lines() if line]

        joined = "\n".join(lines)
        assert '"type": "progress"' in joined
        assert '"type": "delta"' in joined
        assert "streamed assistant text" in joined
        assert '"type": "message"' in joined
        assert '"type": "done"' in joined

        messages = client.get(f"/v1/chat/sessions/{sid}/messages?workspace_id={ws_id}").json()[
            "items"
        ]
        assistant_messages = [
            message
            for message in messages
            if message["role"] == "assistant" and message["content"] == "streamed assistant text"
        ]
        assert len(assistant_messages) == 1

    def test_stream_endpoint_emits_error_for_generation_failure(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        sid = client.post(
            "/v1/chat/sessions", json={"workspace_id": ws_id, "title": "SSE error"}
        ).json()["id"]

        async def fake_stream(*args, **kwargs):
            yield ChatStreamEvent(type="progress")
            yield ChatStreamEvent(type="error", error="forced failure")

        with patch("platform_api.routes.chat.stream_assistant_reply", fake_stream):
            with client.stream(
                "POST",
                f"/v1/chat/sessions/{sid}/messages/stream",
                json={"workspace_id": ws_id, "content": "stream response please"},
            ) as response:
                assert response.status_code == 200
                lines = [line for line in response.iter_lines() if line]

        joined = "\n".join(lines)
        assert '"type": "error"' in joined
        assert '"type": "done"' in joined

    def test_stream_endpoint_emits_done_with_real_generator(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        sid = client.post("/v1/chat/sessions", json={"workspace_id": ws_id, "title": "SSE"}).json()[
            "id"
        ]

        with client.stream(
            "POST",
            f"/v1/chat/sessions/{sid}/messages/stream",
            json={"workspace_id": ws_id, "content": "stream response please"},
        ) as response:
            assert response.status_code == 200
            lines = [line for line in response.iter_lines() if line]

        joined = "\n".join(lines)
        assert '"type": "done"' in joined

    def test_file_upload_persists_metadata(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        sid = client.post(
            "/v1/chat/sessions", json={"workspace_id": ws_id, "title": "Uploads"}
        ).json()["id"]

        files = {"file": ("sample.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}
        form = {"workspace_id": ws_id}
        uploaded = client.post(f"/v1/chat/sessions/{sid}/uploads", data=form, files=files)
        assert uploaded.status_code == 201
        up = uploaded.json()
        assert up["filename"] == "sample.csv"

        listed = client.get(f"/v1/chat/sessions/{sid}/uploads?workspace_id={ws_id}")
        assert listed.status_code == 200
        assert len(listed.json()["items"]) == 1


class TestWorkflowSignals:
    def _create_run(self, client: TestClient, workspace_id: str) -> str:
        with patch(
            "platform_api.routes.runs.create_orchestration_run_id",
            new=AsyncMock(return_value="prefect-flow-run-123"),
        ):
            r = client.post(
                f"/v1/runs?workspace_id={workspace_id}",
                json={"workspace_id": workspace_id, "flow_key": "signal-flow", "parameters": {}},
            )
        assert r.status_code == 201
        assert r.json()["prefect_flow_run_id"] == "prefect-flow-run-123"
        return r.json()["id"]

    def test_emit_and_list_signals(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        run_id = self._create_run(client, ws_id)

        emitted = client.post(
            f"/v1/runs/{run_id}/signals",
            json={
                "workspace_id": ws_id,
                "signal_type": "annotate",
                "target_step": "feature_engineering",
                "note": "check outlier handling",
                "payload": {"priority": "high"},
            },
        )
        assert emitted.status_code == 201
        assert emitted.json()["signal_type"] == "annotate"

        listed = client.get(f"/v1/runs/{run_id}/signals?workspace_id={ws_id}")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["target_step"] == "feature_engineering"

    def test_stream_signals_returns_event(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        run_id = self._create_run(client, ws_id)

        client.post(
            f"/v1/runs/{run_id}/signals",
            json={
                "workspace_id": ws_id,
                "signal_type": "skip",
                "target_step": "eda",
                "payload": {},
            },
        )

        with client.stream(
            "GET", f"/v1/runs/{run_id}/signals/stream?workspace_id={ws_id}"
        ) as response:
            assert response.status_code == 200
            lines = [line for line in response.iter_lines() if line]

        joined = "\n".join(lines)
        assert '"type": "message"' in joined
        assert '"signal_type": "skip"' in joined
        assert '"type": "done"' in joined

    def test_emit_signal_mirrors_into_staged_runtime_store(
        self, admin_client, monkeypatch: pytest.MonkeyPatch
    ):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        run_id = self._create_run(client, ws_id)

        monkeypatch.setattr(
            "platform_api.services.signal_service.settings.orchestration_execution_mode",
            "staged_m22",
        )
        monkeypatch.setattr(
            "platform_api.services.signal_service.settings.orchestration_state_redis_url",
            "redis://runtime-state",
        )

        captured: list[WorkflowSignal] = []

        class _StubSignalStore:
            def emit(self, signal: WorkflowSignal) -> WorkflowSignal:
                captured.append(signal)
                return signal

        monkeypatch.setattr(
            "platform_api.services.signal_service.get_orchestration_signal_store",
            lambda: _StubSignalStore(),
        )

        emitted = client.post(
            f"/v1/runs/{run_id}/signals",
            json={
                "workspace_id": ws_id,
                "signal_type": "annotate",
                "target_step": "feature_engineering",
                "note": "mirror this note",
                "payload": {"priority": "high"},
            },
        )
        assert emitted.status_code == 201

        assert len(captured) == 1
        assert captured[0].session_id == "prefect-flow-run-123"
        assert captured[0].type.value == "annotate"
        assert captured[0].step_id == "feature_engineering"
        assert captured[0].payload["priority"] == "high"
        assert captured[0].payload["note"] == "mirror this note"
