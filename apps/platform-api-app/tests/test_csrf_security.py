from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from platform_api.core.config import settings
from platform_api.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, CsrfProtectionMiddleware
from platform_api.routes.auth import router as auth_router


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CsrfProtectionMiddleware)

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    @app.post("/healthz")
    async def healthz_post():
        return {"ok": True}

    @app.post("/mutate")
    async def mutate():
        return {"ok": True}

    return app


def test_cookie_auth_mutation_requires_csrf():
    client = TestClient(_app())
    response = client.post("/mutate", cookies={"access_token": "dev"})
    assert response.status_code == 403
    assert "CSRF token" in response.json()["detail"]


def test_cookie_auth_mutation_with_matching_csrf_succeeds():
    client = TestClient(_app())
    token = "csrf-test-token"
    response = client.post(
        "/mutate",
        cookies={"access_token": "dev", CSRF_COOKIE_NAME: token},
        headers={CSRF_HEADER_NAME: token},
    )
    assert response.status_code == 200


def test_bearer_mutation_does_not_require_csrf():
    client = TestClient(_app())
    response = client.post(
        "/mutate",
        headers={"Authorization": "Bearer automation-token"},
    )
    assert response.status_code == 200


def test_exempt_path_ignores_csrf():
    previous = settings.csrf_exempt_paths
    settings.csrf_exempt_paths = "/healthz"
    try:
        client = TestClient(_app())
        response = client.post("/healthz", cookies={"access_token": "dev"})
        assert response.status_code == 200
    finally:
        settings.csrf_exempt_paths = previous


def test_csrf_endpoint_issues_cookie_and_payload_token():
    app = FastAPI()
    app.include_router(auth_router)
    client = TestClient(app)

    response = client.get("/v1/auth/csrf")
    assert response.status_code == 200
    body = response.json()
    assert "csrf_token" in body
    assert body["csrf_token"]
    assert CSRF_COOKIE_NAME in response.cookies
