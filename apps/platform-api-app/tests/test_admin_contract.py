from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.authz.dependencies import require_tenant_admin
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
    app.dependency_overrides[require_tenant_admin] = lambda: {
        "user": user,
        "tenant_id": seeded_db["tenant"].id,
        "membership": None,
    }
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db
    app.dependency_overrides.clear()


def test_scheduler_status_returns_restricted_metadata_for_tenant_admin(admin_client):
    client, _seeded_db = admin_client

    response = client.get("/v1/admin/scheduler")

    assert response.status_code == 200
    body = response.json()
    assert body["restricted"] is True
    assert body["message"] == "Scheduler status is restricted to platform operators."
    assert body["is_leader"] is False
    assert body["jobs"] == []


def test_admin_and_finops_routes_require_tenant_admin(app):
    protected_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path.startswith("/v1/admin") or route.path.startswith("/v1/finops"))
    ]

    assert protected_routes, "Expected admin or finops routes to be registered"
    missing = [
        route.path
        for route in protected_routes
        if not any(dependency.call is require_tenant_admin for dependency in route.dependant.dependencies)
    ]

    assert missing == []
