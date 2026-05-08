from __future__ import annotations

from fastapi.testclient import TestClient

from platform_api.main import create_app


def test_healthz_is_canonical_and_health_alias_matches():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    healthz = client.get("/healthz")
    health = client.get("/health")

    assert healthz.status_code == 200
    assert health.status_code == 200
    assert healthz.json() == {"status": "ok"}
    assert health.json() == healthz.json()
