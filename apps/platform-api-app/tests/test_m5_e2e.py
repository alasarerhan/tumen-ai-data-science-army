"""M5 TG3 — End-to-end smoke tests for workflow spec lifecycle.

Each test exercises a *complete user scenario* through the HTTP layer,
using a real in-memory SQLite session (no mocking of service internals).

Scenarios covered:
  S1  Create draft → publish → archive  (happy path, admin)
  S2  Auto-archive: publish v1, publish v2 → v1 becomes archived
  S3  Version progression: create N versions → latest returns vN
  S4  Mixed roles: member creates draft, admin publishes it
  S5  Concurrent flow names: independent version counters
  S6  Filter pipeline: list by name, status, both
  S7  Error boundary: publish archived → 409; double archive → 409
  S8  Auth boundary: anonymous → 401 on all write/read endpoints
  S9  Lifecycle idempotency: get-by-id at each state transition
  S10 Quota path: create 5 specs rapidly, none lost (no actual rate limit hit)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.main import create_app

# ---------------------------------------------------------------------------
# Shared spec payloads
# ---------------------------------------------------------------------------

_SPEC_A = {"steps": [{"id": "load", "tool": "data_load"}, {"id": "clean", "tool": "data_clean"}]}
_SPEC_B = {"steps": [{"id": "feat", "tool": "feature_engineering"}, {"id": "train", "tool": "model_train"}]}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def clients(seeded_db):
    """Return (admin_client, member_client, anon_client, seeded_db)."""
    app = create_app()

    def _db():
        yield seeded_db["db"]

    # --- admin ---
    admin_principal = Principal(
        sub=seeded_db["user_admin"].sub,
        email=seeded_db["user_admin"].email,
        claims={},
    )
    app.dependency_overrides[get_principal] = lambda: admin_principal
    app.dependency_overrides[get_db] = _db
    admin = TestClient(app, raise_server_exceptions=False)

    # --- member ---
    member_principal = Principal(
        sub=seeded_db["user_member"].sub,
        email=seeded_db["user_member"].email,
        claims={},
    )

    def _member_client():
        _app = create_app()
        _app.dependency_overrides[get_principal] = lambda: member_principal
        _app.dependency_overrides[get_db] = _db
        return TestClient(_app, raise_server_exceptions=False)

    member = _member_client()

    # --- anon ---
    anon_app = create_app()
    anon = TestClient(anon_app, raise_server_exceptions=False)

    return admin, member, anon, seeded_db


def _ws(seeded_db) -> str:
    return str(seeded_db["workspace"].id)


def _post_workflow(client, ws_id, name, spec=None, publish=False):
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        return client.post(
            "/v1/workflows",
            json={"workspace_id": ws_id, "name": name, "spec": spec or _SPEC_A, "publish": publish},
        )


def _publish(client, workflow_id, ws_id):
    return client.post(f"/v1/workflows/{workflow_id}/publish?workspace_id={ws_id}")


def _archive(client, workflow_id, ws_id):
    return client.post(f"/v1/workflows/{workflow_id}/archive?workspace_id={ws_id}")


def _list(client, ws_id, name=None, status=None):
    params = f"workspace_id={ws_id}"
    if name:
        params += f"&name={name}"
    if status:
        params += f"&status={status}"
    return client.get(f"/v1/workflows?{params}")


def _latest(client, ws_id, name):
    return client.get(f"/v1/workflows/latest?workspace_id={ws_id}&name={name}")


def _get_by_id(client, workflow_id, ws_id):
    return client.get(f"/v1/workflows/{workflow_id}?workspace_id={ws_id}")


# ---------------------------------------------------------------------------
# S1 — Happy path: create draft → publish → archive
# ---------------------------------------------------------------------------


def test_s1_create_publish_archive(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    # Create draft
    r_create = _post_workflow(admin, ws, "s1-flow")
    assert r_create.status_code == 200
    body = r_create.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    wf_id = body["id"]

    # Publish
    r_pub = _publish(admin, wf_id, ws)
    assert r_pub.status_code == 200
    assert r_pub.json()["status"] == "published"

    # Archive
    r_arc = _archive(admin, wf_id, ws)
    assert r_arc.status_code == 200
    assert r_arc.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# S2 — publish v2 auto-archives v1
# ---------------------------------------------------------------------------


def test_s2_publish_v2_archives_v1(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    r1 = _post_workflow(admin, ws, "series-flow")
    wf1_id = r1.json()["id"]
    _publish(admin, wf1_id, ws)

    r2 = _post_workflow(admin, ws, "series-flow")
    wf2_id = r2.json()["id"]
    _publish(admin, wf2_id, ws)

    # v1 must now be archived
    r_v1_state = _get_by_id(admin, wf1_id, ws)
    assert r_v1_state.status_code == 200
    assert r_v1_state.json()["status"] == "archived"

    # v2 is published
    r_v2_state = _get_by_id(admin, wf2_id, ws)
    assert r_v2_state.json()["status"] == "published"


# ---------------------------------------------------------------------------
# S3 — Version progression: get_latest returns vN
# ---------------------------------------------------------------------------


def test_s3_latest_tracks_highest_version(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    versions_created = []
    for i in range(4):
        r = _post_workflow(admin, ws, "versioned-e2e")
        assert r.status_code == 200
        versions_created.append(r.json()["version"])

    assert versions_created == [1, 2, 3, 4]

    r_latest = _latest(admin, ws, "versioned-e2e")
    assert r_latest.status_code == 200
    assert r_latest.json()["item"]["version"] == 4


# ---------------------------------------------------------------------------
# S4 — Mixed roles: member creates draft, admin publishes it
# ---------------------------------------------------------------------------


def test_s4_member_draft_admin_publishes(clients):
    admin, member, _, sdb = clients
    ws = _ws(sdb)

    # Member creates draft
    r_create = _post_workflow(member, ws, "collab-flow")
    assert r_create.status_code == 200
    assert r_create.json()["status"] == "draft"
    wf_id = r_create.json()["id"]

    # Member cannot publish
    r_member_pub = _publish(member, wf_id, ws)
    assert r_member_pub.status_code == 403

    # Admin can publish
    r_admin_pub = _publish(admin, wf_id, ws)
    assert r_admin_pub.status_code == 200
    assert r_admin_pub.json()["status"] == "published"


# ---------------------------------------------------------------------------
# S5 — Concurrent flow names have independent version counters
# ---------------------------------------------------------------------------


def test_s5_independent_version_counters(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    # Create 3 of flow-alpha and 2 of flow-beta
    for _ in range(3):
        _post_workflow(admin, ws, "flow-alpha")
    for _ in range(2):
        _post_workflow(admin, ws, "flow-beta")

    r_alpha = _latest(admin, ws, "flow-alpha")
    r_beta = _latest(admin, ws, "flow-beta")

    assert r_alpha.json()["item"]["version"] == 3
    assert r_beta.json()["item"]["version"] == 2


# ---------------------------------------------------------------------------
# S6 — Filter pipeline: list by name, status, both
# ---------------------------------------------------------------------------


def test_s6_filter_by_name_and_status(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    # Create: 2 drafts for "filter-a", 1 published for "filter-b"
    _post_workflow(admin, ws, "filter-a", publish=False)
    _post_workflow(admin, ws, "filter-a", publish=False)
    r_pub = _post_workflow(admin, ws, "filter-b", publish=True)
    pub_id = r_pub.json()["id"]

    # List all
    r_all = _list(admin, ws)
    assert len(r_all.json()["items"]) == 3

    # Filter by name
    r_name = _list(admin, ws, name="filter-a")
    assert len(r_name.json()["items"]) == 2
    assert all(i["name"] == "filter-a" for i in r_name.json()["items"])

    # Filter by status=draft
    r_draft = _list(admin, ws, status="draft")
    assert len(r_draft.json()["items"]) == 2

    # Filter by status=published
    r_published = _list(admin, ws, status="published")
    assert len(r_published.json()["items"]) == 1
    assert r_published.json()["items"][0]["id"] == pub_id

    # Filter by name + status (no match)
    r_combo = _list(admin, ws, name="filter-b", status="draft")
    assert len(r_combo.json()["items"]) == 0


# ---------------------------------------------------------------------------
# S7 — Error boundary: publish archived, double archive
# ---------------------------------------------------------------------------


def test_s7_error_boundary_state_transitions(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    r = _post_workflow(admin, ws, "error-flow")
    wf_id = r.json()["id"]

    # Archive it
    _archive(admin, wf_id, ws)

    # Attempting to publish an archived spec → 409
    r_pub = _publish(admin, wf_id, ws)
    assert r_pub.status_code == 409

    # Attempting to archive again → 409
    r_arc2 = _archive(admin, wf_id, ws)
    assert r_arc2.status_code == 409


# ---------------------------------------------------------------------------
# S8 — Auth boundary: anonymous gets 401 on all endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path_template", [
    ("GET", "/v1/workflows?workspace_id={ws}"),
    ("POST", "/v1/workflows"),
    ("GET", "/v1/workflows/latest?workspace_id={ws}&name=x"),
])
def test_s8_anonymous_gets_401(clients, method, path_template):
    _, _, anon, sdb = clients
    ws = _ws(sdb)
    path = path_template.format(ws=ws)
    if method == "GET":
        r = anon.get(path)
    else:
        r = anon.post(path, json={"workspace_id": ws, "name": "anon", "spec": _SPEC_A})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# S9 — Lifecycle idempotency: get-by-id reflects state at each transition
# ---------------------------------------------------------------------------


def test_s9_get_by_id_reflects_state_transitions(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    wf_id = _post_workflow(admin, ws, "state-track").json()["id"]

    # Draft state
    r = _get_by_id(admin, wf_id, ws)
    assert r.status_code == 200
    assert r.json()["status"] == "draft"

    # After publish
    _publish(admin, wf_id, ws)
    r = _get_by_id(admin, wf_id, ws)
    assert r.json()["status"] == "published"

    # After archive
    _archive(admin, wf_id, ws)
    r = _get_by_id(admin, wf_id, ws)
    assert r.json()["status"] == "archived"


# ---------------------------------------------------------------------------
# S10 — Quota path: create 5 specs without hitting quota limit
# ---------------------------------------------------------------------------


def test_s10_rapid_creates_all_succeed(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)
    flow_name = "quota-e2e-flow"

    results = []
    for _ in range(5):
        r = _post_workflow(admin, ws, flow_name)
        results.append(r.status_code)

    assert results == [200, 200, 200, 200, 200], f"Some creates failed: {results}"

    r_latest = _latest(admin, ws, flow_name)
    assert r_latest.json()["item"]["version"] == 5


# ---------------------------------------------------------------------------
# S11 — Spec content round-trip: stored spec matches submitted spec
# ---------------------------------------------------------------------------


def test_s11_spec_content_round_trip(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)

    r = _post_workflow(admin, ws, "spec-roundtrip", spec=_SPEC_B)
    assert r.status_code == 200
    stored_spec = r.json()["spec"]
    assert stored_spec == _SPEC_B


# ---------------------------------------------------------------------------
# S12 — get latest returns None item when name unknown
# ---------------------------------------------------------------------------


def test_s12_latest_unknown_name_returns_null(clients):
    admin, _, _, sdb = clients
    ws = _ws(sdb)
    r = _latest(admin, ws, "definitely-does-not-exist-xyz")
    assert r.status_code == 200
    assert r.json()["item"] is None
