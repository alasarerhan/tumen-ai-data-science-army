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


def test_readiness_and_metrics_are_available():
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)

    ready = client.get("/ready")
    metrics = client.get("/metrics")

    assert ready.status_code == 200
    assert ready.json()["status"] == "ok"
    assert ready.json()["checks"]["database"] == "ok"
    assert metrics.status_code == 200
    assert "text/plain" in metrics.headers["content-type"]
    assert "platform_api_http_requests_total" in metrics.text
