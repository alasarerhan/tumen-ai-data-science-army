from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_api.core.config import settings
from platform_api.routes import artifacts as artifacts_module


def _test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(artifacts_module.router)
    return app


def test_external_artifact_redirect_blocked_when_not_in_allowlist(monkeypatch):
    previous_hosts = settings.artifact_redirect_allowed_hosts
    previous_strict = settings.artifact_redirect_strict_mode
    settings.artifact_redirect_allowed_hosts = "trusted.example.com"
    settings.artifact_redirect_strict_mode = True

    app = _test_app()

    fake_user = SimpleNamespace(id="user-1")
    fake_workspace = SimpleNamespace(id="ws-1")
    fake_artifact = SimpleNamespace(
        id="artifact-1",
        kind="report",
        uri="https://evil.example.com/report",
    )

    def _ctx():
        return {"user": fake_user, "workspace": fake_workspace}

    def _db():
        yield SimpleNamespace()

    monkeypatch.setattr(
        artifacts_module, "get_artifact_for_workspace", lambda *args, **kwargs: fake_artifact
    )
    app.dependency_overrides[artifacts_module.require_workspace_member] = _ctx
    app.dependency_overrides[artifacts_module.get_db] = _db

    try:
        client = TestClient(app)
        response = client.get("/v1/artifacts/artifact-1/access")
        assert response.status_code == 403
    finally:
        settings.artifact_redirect_allowed_hosts = previous_hosts
        settings.artifact_redirect_strict_mode = previous_strict


def test_external_artifact_redirect_allowed_when_host_is_allowlisted(monkeypatch):
    previous_hosts = settings.artifact_redirect_allowed_hosts
    previous_strict = settings.artifact_redirect_strict_mode
    settings.artifact_redirect_allowed_hosts = "trusted.example.com"
    settings.artifact_redirect_strict_mode = True

    app = _test_app()

    fake_user = SimpleNamespace(id="user-1")
    fake_workspace = SimpleNamespace(id="ws-1")
    fake_artifact = SimpleNamespace(
        id="artifact-2",
        kind="report",
        uri="https://trusted.example.com/report",
    )

    def _ctx():
        return {"user": fake_user, "workspace": fake_workspace}

    def _db():
        yield SimpleNamespace()

    monkeypatch.setattr(
        artifacts_module, "get_artifact_for_workspace", lambda *args, **kwargs: fake_artifact
    )
    app.dependency_overrides[artifacts_module.require_workspace_member] = _ctx
    app.dependency_overrides[artifacts_module.get_db] = _db

    try:
        client = TestClient(app)
        response = client.get("/v1/artifacts/artifact-2/access")
        assert response.status_code == 200
        assert response.json()["delivery"]["type"] == "redirect"
    finally:
        settings.artifact_redirect_allowed_hosts = previous_hosts
        settings.artifact_redirect_strict_mode = previous_strict
