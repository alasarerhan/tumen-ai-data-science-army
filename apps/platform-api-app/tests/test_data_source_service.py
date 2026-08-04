from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from platform_api.db.models import Workspace
from platform_api.services import data_source_service


@pytest.mark.parametrize(
    "value",
    [
        str(uuid.uuid4()),
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_parse_uuid_accepts_valid_values(value: str) -> None:
    # Act
    parsed = data_source_service._parse_uuid(value, "workspace_id")

    # Assert
    assert parsed == uuid.UUID(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not-a-uuid",
        "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130",
        "x" * 10000,
    ],
)
def test_parse_uuid_rejects_invalid_values(value: str) -> None:
    # Act / Assert
    with pytest.raises(HTTPException, match=r"Invalid workspace_id") as exc_info:
        data_source_service._parse_uuid(value, "workspace_id")
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        {"schema": "public", "table": "sales"},
        {"unicode": "\u011f\u00fc\u015f\u00f6\u00e7\u0131\u0130", "emoji": "\U0001f4ca"},
    ],
)
def test_create_data_source_persists_fields(
    seeded_db: dict[str, object],
    metadata: dict | None,
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant_id = seeded_db["tenant"].id
    workspace_id = seeded_db["workspace"].id
    user_id = seeded_db["user_admin"].id

    # Act
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        name="sales-ds",
        kind="postgres",
        connection_uri="postgresql://user:pass@db/sales",
        metadata=metadata,
    )

    # Assert
    assert ds.id is not None
    assert ds.workspace_id == workspace_id
    assert ds.created_by_user_id == user_id
    if metadata:
        assert json.loads(ds.metadata_json) == metadata
    else:
        assert ds.metadata_json is None


def test_list_data_sources_filters_workspace_and_orders_desc(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    other_workspace = Workspace(tenant_id=tenant.id, name=f"ds-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()

    first = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="first",
        kind="s3",
        connection_uri="s3://bucket/first",
        metadata=None,
    )
    second = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="second",
        kind="s3",
        connection_uri="s3://bucket/second",
        metadata=None,
    )
    _off_scope = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=other_workspace.id,
        user_id=user_id,
        name="other",
        kind="s3",
        connection_uri="s3://bucket/other",
        metadata=None,
    )
    first.created_at = datetime(2026, 3, 30, 8, 0, tzinfo=UTC)
    second.created_at = datetime(2026, 3, 30, 9, 0, tzinfo=UTC)
    db.add_all([first, second])
    db.flush()

    # Act
    rows = data_source_service.list_data_sources(db, workspace_id=workspace.id)

    # Assert
    assert len(rows) == 2
    assert rows[0].id == second.id
    assert rows[-1].id == first.id


def test_get_data_source_success_and_errors(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    other_workspace = Workspace(tenant_id=tenant.id, name=f"other-{uuid.uuid4().hex[:6]}")
    db.add(other_workspace)
    db.flush()
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="main",
        kind="postgres",
        connection_uri="postgresql://db/main",
        metadata=None,
    )

    # Act
    fetched = data_source_service.get_data_source(
        db,
        ds_id=ds.id,
        workspace_id=workspace.id,
    )

    # Assert
    assert fetched.id == ds.id

    # Act / Assert
    with pytest.raises(HTTPException, match=r"Data source not found") as not_found_exc:
        data_source_service.get_data_source(
            db,
            ds_id=uuid.uuid4(),
            workspace_id=workspace.id,
        )
    assert not_found_exc.value.status_code == 404

    with pytest.raises(HTTPException, match=r"Data source not found") as forbidden_exc:
        data_source_service.get_data_source(
            db,
            ds_id=ds.id,
            workspace_id=other_workspace.id,
        )
    assert forbidden_exc.value.status_code == 404


def test_update_data_source_updates_selected_fields_and_timestamp(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="initial",
        kind="file",
        connection_uri="file://a.csv",
        metadata={"version": 1},
    )
    previous_updated_at = ds.updated_at

    # Act
    updated = data_source_service.update_data_source(
        db,
        ds=ds,
        name="renamed",
        kind="warehouse",
        connection_uri="postgresql://db/new",
        metadata={"version": 2, "note": "updated"},
    )

    # Assert
    assert updated.name == "renamed"
    assert updated.kind == "warehouse"
    assert updated.connection_uri == "postgresql://db/new"
    assert json.loads(updated.metadata_json) == {"version": 2, "note": "updated"}
    assert updated.updated_at is not None
    assert updated.updated_at != previous_updated_at


def test_update_data_source_keeps_fields_when_parameters_are_none(
    seeded_db: dict[str, object],
) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="stable",
        kind="file",
        connection_uri="file://stable.csv",
        metadata={"x": 1},
    )

    # Act
    updated = data_source_service.update_data_source(
        db,
        ds=ds,
        name=None,
        kind=None,
        connection_uri=None,
        metadata=None,
    )

    # Assert
    assert updated.name == "stable"
    assert updated.kind == "file"
    assert updated.connection_uri == "file://stable.csv"
    assert json.loads(updated.metadata_json) == {"x": 1}


def test_delete_data_source_removes_record(seeded_db: dict[str, object]) -> None:
    # Arrange
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="to-delete",
        kind="file",
        connection_uri="file://delete.csv",
        metadata=None,
    )

    # Act
    data_source_service.delete_data_source(db, ds=ds)

    # Assert
    with pytest.raises(HTTPException, match=r"Data source not found"):
        data_source_service.get_data_source(
            db,
            ds_id=ds.id,
            workspace_id=workspace.id,
        )


def test_test_data_source_connection_for_local_file(
    seeded_db: dict[str, object],
    tmp_path: Path,
) -> None:
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    local_dir = tmp_path / "exports"
    local_dir.mkdir()
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="local-files",
        kind="file",
        connection_uri=f"file:///{local_dir.as_posix().lstrip('/')}",
    )

    result = data_source_service.test_data_source_connection(db, ds=ds)

    assert result["status"] == "ok"
    assert "reachable" in result["message"].lower()
    assert "connection_test" in json.loads(ds.metadata_json)


def test_test_data_source_connection_for_sqlite_file(
    seeded_db: dict[str, object],
    tmp_path: Path,
) -> None:
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user_id = seeded_db["user_admin"].id
    sqlite_path = tmp_path / "warehouse.db"
    conn = sqlite3.connect(sqlite_path)
    conn.execute("create table if not exists metrics(id integer primary key)")
    conn.commit()
    conn.close()
    ds = data_source_service.create_data_source(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user_id,
        name="sqlite",
        kind="sql",
        connection_uri=f"sqlite:///{sqlite_path.as_posix().lstrip('/')}",
    )

    result = data_source_service.test_data_source_connection(db, ds=ds)

    assert result["status"] == "ok"
    assert "sqlite" in result["message"].lower()
