from fastapi.testclient import TestClient

from platform_api.main import create_app


def test_frontend_errors_route_accepts_structured_payload() -> None:
    app = create_app()

    with TestClient(app, raise_server_exceptions=False) as client:
        csrf_response = client.get("/v1/auth/csrf")
        assert csrf_response.status_code == 200
        csrf_token = csrf_response.json()["csrf_token"]

        response = client.post(
            "/v1/errors",
            json={
                "message": "Route crashed",
                "name": "Error",
                "route": "/dashboard",
                "source": "route",
                "context": {"feature": "router"},
            },
            headers={"X-CSRF-Token": csrf_token},
        )

    assert response.status_code == 202
    assert response.json() == {"success": True}
    assert response.headers["Cache-Control"] == "no-store"
