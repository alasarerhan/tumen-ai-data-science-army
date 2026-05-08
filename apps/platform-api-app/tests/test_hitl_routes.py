from __future__ import annotations

from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.main import create_app


def _client_for_user(seeded_db, user_key: str):
    app = create_app()
    user = seeded_db[user_key]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal():
        return principal

    def _db():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    return app


def test_member_cannot_approve_hitl_request(seeded_db) -> None:
    app = _client_for_user(seeded_db, "user_member")
    workspace_id = str(seeded_db["workspace"].id)

    with TestClient(app, raise_server_exceptions=False) as client:
        created = client.post(
            "/v1/hitl",
            json={
                "workspace_id": workspace_id,
                "step_key": "prod-deploy",
                "payload": {"target": "production"},
                "expires_hours": 24,
            },
        )
        assert created.status_code == 201

        approval_id = created.json()["id"]
        approved = client.post(
            f"/v1/hitl/{approval_id}/approve",
            json={"workspace_id": workspace_id, "comment": "member self approval"},
        )
        assert approved.status_code == 403
        assert "admin or owner" in approved.json()["detail"].lower()

    app.dependency_overrides.clear()
