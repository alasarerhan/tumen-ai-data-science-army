from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.main import create_app
from platform_api.routes import logs as logs_module
from platform_api.services.run_service import create_workflow_run_record


@pytest.fixture()
def client_and_run(seeded_db):
    app = create_app()
    user = seeded_db["user_admin"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal():
        return principal

    def _db():
        yield seeded_db["db"]

    run = create_workflow_run_record(
        seeded_db["db"],
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=user.id,
        flow_key="test-flow",
        prefect_flow_run_id="prefect-log-test",
        parameters={},
    )
    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db, run
    app.dependency_overrides.clear()


def test_logs_endpoint_rejects_mock_fallback_in_release_profile(client_and_run, monkeypatch):
    client, seeded_db, run = client_and_run
    monkeypatch.setattr(logs_module.settings, "deployment_profile", "release")
    monkeypatch.setattr(logs_module.settings, "allow_local_run_fallback", False)

    response = client.get(f"/v1/runs/{run.id}/logs?workspace_id={seeded_db['workspace'].id}")

    assert response.status_code == 503
    assert response.json()["detail"] == "Run log stream is unavailable"


def test_logs_endpoint_allows_mock_fallback_in_local_profile(client_and_run, monkeypatch):
    client, seeded_db, run = client_and_run
    monkeypatch.setattr(logs_module.settings, "deployment_profile", "local")
    monkeypatch.setattr(logs_module.settings, "allow_local_run_fallback", True)

    async def quick_mock_stream(run_id: str, run_status: str):
        yield await logs_module._sse_event(
            {"msg": f"Run {run_id} finished with status: {run_status}"}
        )

    monkeypatch.setattr(logs_module, "_mock_log_stream", quick_mock_stream)

    response = client.get(f"/v1/runs/{run.id}/logs?workspace_id={seeded_db['workspace'].id}")

    assert response.status_code == 200
    assert "Run" in response.text
