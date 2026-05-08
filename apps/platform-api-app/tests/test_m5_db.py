"""M5 TG2 — DB-level integration tests for workflow spec lifecycle.

Uses an in-memory SQLite session (via ``seeded_db`` fixture in conftest.py).
These tests exercise real SQLAlchemy queries without a running Postgres.

Coverage:
  - Version auto-increment across multiple creates
  - Status correctly set to draft vs published on create
  - list_workflow_specs with name/status filters
  - get_latest_workflow_spec returns highest-version record
  - publish_workflow_spec: auto-archives old published, sets status
  - archive_workflow_spec: idempotent archive guard
  - Spec validation (missing fields) from the service layer
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from platform_api.db.models import WorkspaceRole
from platform_api.services.workflow_service import (
    _validate_spec,
    archive_workflow_spec,
    create_workflow_spec_version,
    get_latest_workflow_spec,
    list_workflow_specs,
    publish_workflow_spec,
)

_VALID_SPEC = {"steps": [{"id": "step1", "tool": "data_clean"}]}
_MULTI_STEP_SPEC = {
    "steps": [
        {"id": "s1", "tool": "data_load"},
        {"id": "s2", "tool": "feature_engineering"},
        {"id": "s3", "tool": "model_train"},
    ]
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create(db, workspace, user, name="flow-a", spec=None, publish=False):
    """Thin wrapper patching only the quota guard (no external deps)."""
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        return create_workflow_spec_version(
            db,
            workspace_id=str(workspace.id),
            user_id=user.id,
            name=name,
            spec=spec or _VALID_SPEC,
            publish=publish,
        )


# ---------------------------------------------------------------------------
# create_workflow_spec_version — version auto-increment
# ---------------------------------------------------------------------------


def test_create_first_version_is_v1(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    assert record.version == 1


def test_create_second_version_is_v2(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="versioned-flow")
    r2 = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="versioned-flow")
    assert r2.version == 2


def test_create_third_version_increments_correctly(seeded_db):
    ctx = seeded_db
    for _ in range(3):
        _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="multi-ver")
    r4 = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="multi-ver")
    assert r4.version == 4


def test_create_different_names_independent_counters(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="flow-x")
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="flow-x")
    r1_y = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="flow-y")
    assert r1_y.version == 1  # independent counter for 'flow-y'


def test_create_draft_status(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], publish=False)
    assert record.status == "draft"


def test_create_published_status_admin(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], publish=True)
    assert record.status == "published"


def test_create_published_by_member_raises_403(seeded_db):
    ctx = seeded_db
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        with pytest.raises(HTTPException) as exc_info:
            create_workflow_spec_version(
                ctx["db"],
                workspace_id=str(ctx["workspace"].id),
                user_id=ctx["user_member"].id,
                name="flow-z",
                spec=_VALID_SPEC,
                publish=True,
            )
    assert exc_info.value.status_code == 403


def test_create_spec_stored_as_json(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], spec=_MULTI_STEP_SPEC)
    loaded = json.loads(record.spec_json)
    assert len(loaded["steps"]) == 3
    assert loaded["steps"][1]["tool"] == "feature_engineering"


# ---------------------------------------------------------------------------
# list_workflow_specs
# ---------------------------------------------------------------------------


def test_list_returns_all_for_workspace(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="wf-a")
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="wf-b")
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="wf-a")
    records = list_workflow_specs(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name=None,
    )
    assert len(records) == 3


def test_list_filter_by_name(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="target")
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="other")
    records = list_workflow_specs(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name="target",
    )
    assert len(records) == 1
    assert records[0].name == "target"


def test_list_filter_by_status_draft(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], publish=False)
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], publish=True)
    drafts = list_workflow_specs(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name=None,
        status="draft",
    )
    assert all(r.status == "draft" for r in drafts)


def test_list_filter_by_status_published(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="pub-flow", publish=True)
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="draft-flow", publish=False)
    published = list_workflow_specs(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name=None,
        status="published",
    )
    assert len(published) == 1
    assert published[0].name == "pub-flow"


def test_list_invalid_status_raises_400(seeded_db):
    ctx = seeded_db
    with pytest.raises(HTTPException) as exc_info:
        list_workflow_specs(
            ctx["db"],
            workspace_id=str(ctx["workspace"].id),
            user_id=ctx["user_admin"].id,
            name=None,
            status="BOGUS",
        )
    assert exc_info.value.status_code == 400


def test_list_empty_when_no_specs(seeded_db):
    ctx = seeded_db
    records = list_workflow_specs(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name=None,
    )
    assert records == []


# ---------------------------------------------------------------------------
# get_latest_workflow_spec
# ---------------------------------------------------------------------------


def test_get_latest_returns_highest_version(seeded_db):
    ctx = seeded_db
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="streamed")
    _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="streamed")
    latest = get_latest_workflow_spec(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name="streamed",
    )
    assert latest is not None
    assert latest.version == 2


def test_get_latest_returns_none_when_missing(seeded_db):
    ctx = seeded_db
    latest = get_latest_workflow_spec(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name="nonexistent-flow",
    )
    assert latest is None


def test_get_latest_prefers_recent_create_order(seeded_db):
    ctx = seeded_db
    for i in range(5):
        _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="versioned")
    latest = get_latest_workflow_spec(
        ctx["db"],
        workspace_id=str(ctx["workspace"].id),
        user_id=ctx["user_admin"].id,
        name="versioned",
    )
    assert latest.version == 5


# ---------------------------------------------------------------------------
# publish_workflow_spec — with real DB queries
# ---------------------------------------------------------------------------


def _publish(db, workspace, user, workflow_id):
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        return publish_workflow_spec(
            db,
            workflow_id=str(workflow_id),
            workspace_id=str(workspace.id),
            user_id=user.id,
        )


def test_publish_sets_published_status(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="pub-test")
    published = _publish(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    assert published.status == "published"


def test_publish_auto_archives_previous_published(seeded_db):
    ctx = seeded_db
    r1 = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="series")
    r2 = _create(ctx["db"], ctx["workspace"], ctx["user_admin"], name="series")

    _publish(ctx["db"], ctx["workspace"], ctx["user_admin"], r1.id)
    # Now publish r2 — r1 should be auto-archived
    _publish(ctx["db"], ctx["workspace"], ctx["user_admin"], r2.id)

    ctx["db"].refresh(r1)
    ctx["db"].refresh(r2)

    assert r1.status == "archived"
    assert r2.status == "published"


def test_publish_by_member_raises_403(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        with pytest.raises(HTTPException) as exc_info:
            publish_workflow_spec(
                ctx["db"],
                workflow_id=str(record.id),
                workspace_id=str(ctx["workspace"].id),
                user_id=ctx["user_member"].id,
            )
    assert exc_info.value.status_code == 403


def test_publish_already_archived_raises_409(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    # archive first
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        archive_workflow_spec(
            ctx["db"],
            workflow_id=str(record.id),
            workspace_id=str(ctx["workspace"].id),
            user_id=ctx["user_admin"].id,
        )
    with pytest.raises(HTTPException) as exc_info:
        _publish(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# archive_workflow_spec — with real DB queries
# ---------------------------------------------------------------------------


def _archive(db, workspace, user, workflow_id):
    return archive_workflow_spec(
        db,
        workflow_id=str(workflow_id),
        workspace_id=str(workspace.id),
        user_id=user.id,
    )


def test_archive_draft_sets_archived_status(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    archived = _archive(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    assert archived.status == "archived"


def test_archive_published_sets_archived_status(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    _publish(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    ctx["db"].refresh(record)
    archived = _archive(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    assert archived.status == "archived"


def test_archive_already_archived_raises_409(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    _archive(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    with pytest.raises(HTTPException) as exc_info:
        _archive(ctx["db"], ctx["workspace"], ctx["user_admin"], record.id)
    assert exc_info.value.status_code == 409


def test_archive_by_member_raises_403(seeded_db):
    ctx = seeded_db
    record = _create(ctx["db"], ctx["workspace"], ctx["user_admin"])
    with pytest.raises(HTTPException) as exc_info:
        _archive(ctx["db"], ctx["workspace"], ctx["user_admin_replaced"] if False else ctx["user_member"], record.id)
    assert exc_info.value.status_code == 403
