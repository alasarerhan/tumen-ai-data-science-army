from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.main import create_app


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


def test_post_runs_uses_orchestration_service(admin_client):
    client, sdb = admin_client
    ws_id = str(sdb["workspace"].id)

    with patch(
        "platform_api.routes.runs.create_orchestration_run_id",
        new=AsyncMock(return_value="prefect-prod-run-abc123"),
    ):
        resp = client.post(
            f"/v1/runs?workspace_id={ws_id}",
            json={"workspace_id": ws_id, "flow_key": "hello", "parameters": {"a": 1}},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["prefect_flow_run_id"] == "prefect-prod-run-abc123"
    assert not body["prefect_flow_run_id"].startswith("local-")


def test_post_runs_propagates_orchestration_contract_error(admin_client):
    client, sdb = admin_client
    ws_id = str(sdb["workspace"].id)

    with patch(
        "platform_api.routes.runs.create_orchestration_run_id",
        new=AsyncMock(side_effect=HTTPException(status_code=400, detail="Missing deployment id")),
    ):
        resp = client.post(
            f"/v1/runs?workspace_id={ws_id}",
            json={"workspace_id": ws_id, "flow_key": "unknown-flow", "parameters": {}},
        )

    assert resp.status_code == 400
    assert "Missing deployment id" in resp.text


def test_prefect_compat_endpoint_is_deprecated_but_uses_same_orchestration(admin_client):
    client, sdb = admin_client
    ws_id = str(sdb["workspace"].id)

    with patch(
        "platform_api.routes.prefect.create_orchestration_run_id",
        new=AsyncMock(return_value="prefect-hello-compat-1"),
    ):
        resp = client.post(
            "/v1/prefect/hello-runs",
            json={"workspace_id": ws_id, "parameters": {"source": "compat-test"}},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["flow_run_id"] == "prefect-hello-compat-1"
    assert body["deprecated"] is True
