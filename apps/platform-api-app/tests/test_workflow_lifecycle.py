"""Unit tests for workflow spec version lifecycle (M5).

These tests are pure-unit: they mock the SQLAlchemy session so no database is
required.  They exercise the business-logic rules defined in workflow_service.py:

  - Version auto-increment on create
  - Publish guards (non-admin forbidden, archived blocked)
  - Auto-archive of older published versions on new publish
  - Explicit archive guard (already archived → 409)
  - Status parameter filter forwarded to query
"""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import HTTPException

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_workspace(tenant_id=None):
    ws = MagicMock()
    ws.id = uuid.uuid4()
    ws.tenant_id = tenant_id or uuid.uuid4()
    return ws


def _make_membership(role: str = "admin"):
    m = MagicMock()
    m.role = role
    return m


def _make_spec_record(
    name: str = "my-flow",
    version: int = 1,
    status: str = "draft",
    workspace_id=None,
):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.name = name
    r.version = version
    r.status = status
    r.workspace_id = workspace_id or uuid.uuid4()
    r.spec_json = json.dumps({"steps": [{"id": "s1", "tool": "echo"}]})
    return r


# ── _validate_spec ────────────────────────────────────────────────────────────


from platform_api.services.workflow_service import _validate_spec  # noqa: E402


def test_validate_spec_ok():
    _validate_spec({"name": "Steps flow", "steps": [{"id": "s1", "tool": "data_clean"}]})


def test_validate_graph_spec_ok():
    _validate_spec(
        {
            "name": "Graph flow",
            "graph": {
                "nodes": [
                    {"id": "n1", "label": "Data Loader", "agent": "DataLoaderToolsAgent"},
                    {"id": "n2", "label": "Data Cleaning", "agent": "DataCleaningAgent"},
                ],
                "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
            },
        }
    )


def test_validate_spec_missing_steps():
    with pytest.raises(HTTPException) as exc_info:
        _validate_spec({"name": "Broken"})
    assert exc_info.value.status_code == 400
    assert "graph.nodes" in exc_info.value.detail.lower() or "steps array" in exc_info.value.detail.lower()


def test_validate_spec_empty_steps():
    with pytest.raises(HTTPException) as exc_info:
        _validate_spec({"name": "Broken", "steps": []})
    assert exc_info.value.status_code == 400


def test_validate_spec_step_missing_tool():
    with pytest.raises(HTTPException) as exc_info:
        _validate_spec({"name": "Broken", "steps": [{"id": "s1"}]})
    assert exc_info.value.status_code == 400
    assert "known agent" in exc_info.value.detail.lower() or "graph.nodes" in exc_info.value.detail.lower()


def test_validate_spec_rejects_blocked_chain():
    with pytest.raises(HTTPException) as exc_info:
        _validate_spec(
            {
                "name": "Blocked",
                "graph": {
                    "nodes": [
                        {"id": "n1", "label": "Visualization", "agent": "DataVisualizationAgent"},
                        {"id": "n2", "label": "H2O ML", "agent": "H2OMLAgent"},
                    ],
                    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
                },
            }
        )
    assert exc_info.value.status_code == 400
    assert "cannot chain directly" in exc_info.value.detail.lower()


# ── publish lifecycle ─────────────────────────────────────────────────────────


from platform_api.services.workflow_service import (  # noqa: E402
    _auto_archive_published,
    archive_workflow_spec,
    publish_workflow_spec,
)


def _patch_helpers(workspace, membership, record):
    """Return a context-manager that patches _authorized_workspace and
    get_workflow_spec_for_workspace for the given objects."""
    patcher_ws = patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(workspace, membership),
    )
    patcher_get = patch(
        "platform_api.services.workflow_service.get_workflow_spec_for_workspace",
        return_value=record,
    )
    patcher_quota = patch(
        "platform_api.services.workflow_service.enforce_tenant_write_quota"
    )
    return patcher_ws, patcher_get, patcher_quota


def test_publish_non_admin_raises_403():
    ws = _make_workspace()
    membership = _make_membership(role="member")
    record = _make_spec_record(status="draft", workspace_id=ws.id)
    db = MagicMock()

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ), patch(
        "platform_api.services.workflow_service.get_workflow_spec_for_workspace",
        return_value=record,
    ), patch(
        "platform_api.services.workflow_service.enforce_tenant_write_quota"
    ):
        with pytest.raises(HTTPException) as exc_info:
            publish_workflow_spec(
                db,
                workflow_id=str(record.id),
                workspace_id=str(ws.id),
                user_id=uuid.uuid4(),
            )
    assert exc_info.value.status_code == 403


def test_publish_archived_spec_raises_409():
    ws = _make_workspace()
    membership = _make_membership(role="admin")
    record = _make_spec_record(status="archived", workspace_id=ws.id)
    db = MagicMock()

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ), patch(
        "platform_api.services.workflow_service.get_workflow_spec_for_workspace",
        return_value=record,
    ), patch(
        "platform_api.services.workflow_service.enforce_tenant_write_quota"
    ):
        with pytest.raises(HTTPException) as exc_info:
            publish_workflow_spec(
                db,
                workflow_id=str(record.id),
                workspace_id=str(ws.id),
                user_id=uuid.uuid4(),
            )
    assert exc_info.value.status_code == 409


def test_publish_sets_status_published_and_archives_old(monkeypatch):
    ws = _make_workspace()
    membership = _make_membership(role="admin")
    record = _make_spec_record(name="flow", version=2, status="draft", workspace_id=ws.id)
    db = MagicMock()

    archived_calls = []

    def fake_auto_archive(db, *, workspace_id, name, exclude_id):
        archived_calls.append((workspace_id, name, exclude_id))
        return 1

    monkeypatch.setattr(
        "platform_api.services.workflow_service._auto_archive_published",
        fake_auto_archive,
    )

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ), patch(
        "platform_api.services.workflow_service.get_workflow_spec_for_workspace",
        return_value=record,
    ), patch(
        "platform_api.services.workflow_service.enforce_tenant_write_quota"
    ):
        result = publish_workflow_spec(
            db,
            workflow_id=str(record.id),
            workspace_id=str(ws.id),
            user_id=uuid.uuid4(),
        )

    assert result.status == "published"
    # auto-archive was called exactly once
    assert len(archived_calls) == 1
    _, name, exclude_id = archived_calls[0]
    assert name == "flow"
    assert exclude_id == record.id


# ── archive lifecycle ─────────────────────────────────────────────────────────


def test_archive_already_archived_raises_409():
    ws = _make_workspace()
    membership = _make_membership(role="admin")
    record = _make_spec_record(status="archived", workspace_id=ws.id)
    db = MagicMock()

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ), patch(
        "platform_api.services.workflow_service.get_workflow_spec_for_workspace",
        return_value=record,
    ):
        with pytest.raises(HTTPException) as exc_info:
            archive_workflow_spec(
                db,
                workflow_id=str(record.id),
                workspace_id=str(ws.id),
                user_id=uuid.uuid4(),
            )
    assert exc_info.value.status_code == 409


def test_archive_draft_succeeds():
    ws = _make_workspace()
    membership = _make_membership(role="admin")
    record = _make_spec_record(status="draft", workspace_id=ws.id)
    db = MagicMock()

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ), patch(
        "platform_api.services.workflow_service.get_workflow_spec_for_workspace",
        return_value=record,
    ):
        result = archive_workflow_spec(
            db,
            workflow_id=str(record.id),
            workspace_id=str(ws.id),
            user_id=uuid.uuid4(),
        )

    assert result.status == "archived"
    db.add.assert_called_once_with(record)
    db.flush.assert_called_once()


def test_archive_non_admin_raises_403():
    ws = _make_workspace()
    membership = _make_membership(role="viewer")
    record = _make_spec_record(status="draft", workspace_id=ws.id)
    db = MagicMock()

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ):
        with pytest.raises(HTTPException) as exc_info:
            archive_workflow_spec(
                db,
                workflow_id=str(record.id),
                workspace_id=str(ws.id),
                user_id=uuid.uuid4(),
            )
    assert exc_info.value.status_code == 403


# ── list_workflow_specs status filter ─────────────────────────────────────────


from platform_api.services.workflow_service import list_workflow_specs  # noqa: E402


def test_list_invalid_status_raises_400():
    ws = _make_workspace()
    membership = _make_membership(role="member")
    db = MagicMock()

    with patch(
        "platform_api.services.workflow_service._authorized_workspace",
        return_value=(ws, membership),
    ):
        with pytest.raises(HTTPException) as exc_info:
            list_workflow_specs(
                db,
                workspace_id=str(ws.id),
                user_id=uuid.uuid4(),
                name=None,
                status="invalid_status",
            )
    assert exc_info.value.status_code == 400
