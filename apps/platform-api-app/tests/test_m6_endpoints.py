"""M6 TG2 — HTTP-level RBAC policy matrix tests via FastAPI TestClient.

Each endpoint is exercised with:
  * admin principal  → expects 2xx
  * member principal → expects 403 on admin-only endpoints
  * unauthenticated  → expects 401

Dependencies overridden per test via ``app.dependency_overrides``:
  * ``get_principal`` → returns a ``Principal`` whose sub matches the seeded DB user
  * ``get_db``        → yields the in-memory SQLite session from ``seeded_db``

The ``enforce_tenant_write_quota`` function is patched for write operations.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.models import WorkflowSpec
from platform_api.db.session import get_db
from platform_api.main import create_app

_VALID_SPEC = {
    "name": "valid-endpoint-workflow",
    "steps": [{"id": "s1", "tool": "Data Cleaning", "agent": "DataCleaningAgent"}],
}


# ---------------------------------------------------------------------------
# Fixtures — create per-test TestClient instances with dep overrides
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Fresh FastAPI app per test (avoids shared override state)."""
    return create_app()


@pytest.fixture()
def admin_client(app, seeded_db):
    """TestClient authenticated as the workspace-admin user."""
    user = seeded_db["user_admin"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _get_principal_override():
        return principal

    def _get_db_override():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _get_principal_override
    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db
    app.dependency_overrides.clear()


@pytest.fixture()
def member_client(app, seeded_db):
    """TestClient authenticated as the workspace-member user."""
    user = seeded_db["user_member"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _get_principal_override():
        return principal

    def _get_db_override():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _get_principal_override
    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db
    app.dependency_overrides.clear()


@pytest.fixture()
def anon_client(app):
    """TestClient with no auth headers (anonymous)."""
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_workflow_in_db(seeded_db, name="endpoint-flow", publish=False):
    """Create a WorkflowSpec directly via the service (bypasses HTTP)."""
    from unittest.mock import patch as _patch

    from platform_api.services.workflow_service import create_workflow_spec_version

    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]

    with _patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        record = create_workflow_spec_version(
            seeded_db["db"],
            workspace_id=str(workspace.id),
            user_id=user.id,
            name=name,
            spec=_VALID_SPEC,
            publish=publish,
        )
    return record


# ---------------------------------------------------------------------------
# GET /v1/workflows — member required
# ---------------------------------------------------------------------------


class TestGetWorkflowsEndpoint:
    def test_admin_can_get_chain_rules(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows/chain-rules?workspace_id={ws_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["workspace_id"] == ws_id
        assert body["ruleset"]["version"] == "1.0.0"
        assert any(item["key"] == "DataCleaningAgent" for item in body["catalog"])

    def test_member_can_get_chain_rules(self, member_client):
        client, sdb = member_client
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows/chain-rules?workspace_id={ws_id}")
        assert r.status_code == 200

    def test_anon_cannot_get_chain_rules(self, anon_client, seeded_db):
        ws_id = str(seeded_db["workspace"].id)
        r = anon_client.get(f"/v1/workflows/chain-rules?workspace_id={ws_id}")
        assert r.status_code == 401

    def test_admin_can_list_workflows(self, admin_client):
        client, sdb = admin_client
        _create_workflow_in_db(sdb, name="list-flow")
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows?workspace_id={ws_id}")
        assert r.status_code == 200
        assert "items" in r.json()
        assert "validation_summary" in r.json()["items"][0]

    def test_member_can_list_workflows(self, member_client):
        client, sdb = member_client
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows?workspace_id={ws_id}")
        assert r.status_code == 200

    def test_anon_cannot_list_workflows(self, anon_client, seeded_db):
        ws_id = str(seeded_db["workspace"].id)
        r = anon_client.get(f"/v1/workflows?workspace_id={ws_id}")
        assert r.status_code == 401

    def test_list_filters_by_name(self, admin_client):
        client, sdb = admin_client
        _create_workflow_in_db(sdb, name="my-named-flow")
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows?workspace_id={ws_id}&name=my-named-flow")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        assert all(i["name"] == "my-named-flow" for i in items)

    def test_list_invalid_workspace_id(self, admin_client):
        client, _ = admin_client
        r = client.get("/v1/workflows?workspace_id=not-a-uuid")
        assert r.status_code == 400

    def test_list_nonexistent_workspace_returns_404(self, admin_client):
        import uuid as _uuid

        client, _ = admin_client
        r = client.get(f"/v1/workflows?workspace_id={_uuid.uuid4()}")
        assert r.status_code in (403, 404)


# ---------------------------------------------------------------------------
# POST /v1/workflows — member creates drafts; only admin can publish
# ---------------------------------------------------------------------------


class TestCreateWorkflowEndpoint:
    def test_admin_creates_draft(self, admin_client):
        client, sdb = admin_client
        with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
            r = client.post(
                "/v1/workflows",
                json={
                    "workspace_id": str(sdb["workspace"].id),
                    "name": "http-flow",
                    "spec": _VALID_SPEC,
                    "publish": False,
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "draft"
        assert body["version"] == 1
        assert body["validation_summary"]["status"] == "safe"

    def test_admin_creates_published(self, admin_client):
        client, sdb = admin_client
        with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
            r = client.post(
                "/v1/workflows",
                json={
                    "workspace_id": str(sdb["workspace"].id),
                    "name": "pub-http-flow",
                    "spec": _VALID_SPEC,
                    "publish": True,
                },
            )
        assert r.status_code == 200
        assert r.json()["status"] == "published"

    def test_member_creates_draft(self, member_client):
        client, sdb = member_client
        with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
            r = client.post(
                "/v1/workflows",
                json={
                    "workspace_id": str(sdb["workspace"].id),
                    "name": "member-http-flow",
                    "spec": _VALID_SPEC,
                    "publish": False,
                },
            )
        assert r.status_code == 200
        assert r.json()["status"] == "draft"

    def test_member_publish_raises_403(self, member_client):
        client, sdb = member_client
        with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
            r = client.post(
                "/v1/workflows",
                json={
                    "workspace_id": str(sdb["workspace"].id),
                    "name": "member-publish-attempt",
                    "spec": _VALID_SPEC,
                    "publish": True,
                },
            )
        assert r.status_code == 403

    def test_anon_create_returns_401(self, anon_client, seeded_db):
        r = anon_client.post(
            "/v1/workflows",
            json={
                "workspace_id": str(seeded_db["workspace"].id),
                "name": "anon-flow",
                "spec": _VALID_SPEC,
                "publish": False,
            },
        )
        assert r.status_code == 401

    def test_second_create_increments_version(self, admin_client):
        client, sdb = admin_client
        payload = {
            "workspace_id": str(sdb["workspace"].id),
            "name": "versioned-http",
            "spec": _VALID_SPEC,
            "publish": False,
        }
        with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
            r1 = client.post("/v1/workflows", json=payload)
            r2 = client.post("/v1/workflows", json=payload)
        assert r1.json()["version"] == 1
        assert r2.json()["version"] == 2


# ---------------------------------------------------------------------------
# POST /v1/workflows/{id}/publish — admin/owner required
# ---------------------------------------------------------------------------


class TestPublishWorkflowEndpoint:
    def test_admin_can_publish(self, admin_client):
        client, sdb = admin_client
        record = _create_workflow_in_db(sdb)
        r = client.post(f"/v1/workflows/{record.id}/publish?workspace_id={sdb['workspace'].id}")
        assert r.status_code == 200
        assert r.json()["status"] == "published"

    def test_member_cannot_publish(self, member_client):
        client, sdb = member_client
        record = _create_workflow_in_db(sdb)
        r = client.post(f"/v1/workflows/{record.id}/publish?workspace_id={sdb['workspace'].id}")
        assert r.status_code == 403

    def test_anon_cannot_publish(self, anon_client, seeded_db):
        record = _create_workflow_in_db(seeded_db)
        r = anon_client.post(
            f"/v1/workflows/{record.id}/publish?workspace_id={seeded_db['workspace'].id}"
        )
        assert r.status_code == 401

    def test_publish_already_archived_returns_409(self, admin_client):
        client, sdb = admin_client
        record = _create_workflow_in_db(sdb)
        # archive via db first
        from platform_api.services.workflow_service import archive_workflow_spec

        archive_workflow_spec(
            sdb["db"],
            workflow_id=str(record.id),
            workspace_id=str(sdb["workspace"].id),
            user_id=sdb["user_admin"].id,
        )
        r = client.post(f"/v1/workflows/{record.id}/publish?workspace_id={sdb['workspace'].id}")
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /v1/workflows/{id}/archive — admin/owner required
# ---------------------------------------------------------------------------


class TestArchiveWorkflowEndpoint:
    def test_admin_can_archive(self, admin_client):
        client, sdb = admin_client
        record = _create_workflow_in_db(sdb)
        r = client.post(f"/v1/workflows/{record.id}/archive?workspace_id={sdb['workspace'].id}")
        assert r.status_code == 200
        assert r.json()["status"] == "archived"

    def test_member_cannot_archive(self, member_client):
        client, sdb = member_client
        record = _create_workflow_in_db(sdb)
        r = client.post(f"/v1/workflows/{record.id}/archive?workspace_id={sdb['workspace'].id}")
        assert r.status_code == 403

    def test_anon_cannot_archive(self, anon_client, seeded_db):
        record = _create_workflow_in_db(seeded_db)
        r = anon_client.post(
            f"/v1/workflows/{record.id}/archive?workspace_id={seeded_db['workspace'].id}"
        )
        assert r.status_code == 401

    def test_archive_twice_returns_409(self, admin_client):
        client, sdb = admin_client
        record = _create_workflow_in_db(sdb)
        ws = str(sdb["workspace"].id)
        client.post(f"/v1/workflows/{record.id}/archive?workspace_id={ws}")
        r2 = client.post(f"/v1/workflows/{record.id}/archive?workspace_id={ws}")
        assert r2.status_code == 409


# ---------------------------------------------------------------------------
# GET /v1/workflows/latest — member required
# ---------------------------------------------------------------------------


class TestGetLatestWorkflowEndpoint:
    def test_admin_gets_latest(self, admin_client):
        client, sdb = admin_client
        _create_workflow_in_db(sdb, name="latest-test")
        _create_workflow_in_db(sdb, name="latest-test")
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows/latest?workspace_id={ws_id}&name=latest-test")
        assert r.status_code == 200
        assert r.json()["item"]["version"] == 2
        assert r.json()["item"]["validation_summary"]["status"] == "safe"

    def test_member_gets_latest(self, member_client):
        client, sdb = member_client
        _create_workflow_in_db(sdb, name="latest-member")
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows/latest?workspace_id={ws_id}&name=latest-member")
        assert r.status_code == 200

    def test_missing_name_returns_422(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows/latest?workspace_id={ws_id}")
        assert r.status_code == 422

    def test_nonexistent_name_returns_null_item(self, admin_client):
        client, sdb = admin_client
        ws_id = str(sdb["workspace"].id)
        r = client.get(f"/v1/workflows/latest?workspace_id={ws_id}&name=does-not-exist")
        assert r.status_code == 200
        assert r.json()["item"] is None


class TestTriggerWorkflowEndpoint:
    def test_invalid_workflow_cannot_trigger(self, admin_client):
        client, sdb = admin_client
        db = sdb["db"]
        workspace = sdb["workspace"]
        user = sdb["user_admin"]
        invalid_spec = {
            "name": "invalid-chain",
            "steps": [
                {"id": "viz", "agent": "Visualization", "instruction": "Plot the dataset."},
                {
                    "id": "model",
                    "agent": "H2O ML",
                    "instruction": "Train a model.",
                    "depends_on": ["viz"],
                },
            ],
        }
        record = WorkflowSpec(
            id=uuid.uuid4(),
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            name="invalid-chain",
            version=1,
            status="draft",
            spec_json=json.dumps(invalid_spec),
            created_by_user_id=user.id,
        )
        db.add(record)
        db.commit()

        r = client.post(f"/v1/workflows/{record.id}/trigger?workspace_id={workspace.id}")

        assert r.status_code == 400
        assert "invalid agent chains" in r.json()["detail"].lower()
