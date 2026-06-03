from __future__ import annotations

import json

import pytest

from platform_api.db.models import DataSourceSecret
from platform_api.routes.data_sources import _ds_to_dict
from platform_api.services.data_source_service import create_data_source
from platform_api.services.data_source_service import test_data_source_connection as run_connection_test


def test_sql_server_data_source_masks_secret_metadata(seeded_db):
    db = seeded_db["db"]
    ds = create_data_source(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        name="Finance SQL Server",
        kind="sql_server",
        connection_uri=None,
        metadata={
            "provider": "sql_server",
            "host": "sql.internal",
            "port": 1433,
            "database": "finance",
            "username": "analyst",
            "password": "super-secret-password",
            "encrypt": True,
            "trust_server_certificate": False,
        },
    )

    payload = _ds_to_dict(ds)
    stored_metadata = json.loads(ds.metadata_json)

    assert payload["kind"] == "sql_server"
    assert "super-secret-password" not in payload["connection_uri"]
    assert "password" not in payload["metadata"]
    assert "secret_ref" not in payload["metadata"]
    assert payload["metadata"]["has_secret"] is True
    assert stored_metadata["secret_ref"].startswith("data-source-secret-")
    assert db.query(DataSourceSecret).filter(DataSourceSecret.workspace_id == seeded_db["workspace"].id).count() == 1
    assert "super-secret-password" not in db.query(DataSourceSecret).one().encrypted_value


def test_sql_server_requires_structured_connection_fields(seeded_db):
    with pytest.raises(ValueError, match="host, database, and username"):
        create_data_source(
            seeded_db["db"],
            tenant_id=seeded_db["tenant"].id,
            workspace_id=seeded_db["workspace"].id,
            user_id=seeded_db["user_admin"].id,
            name="Broken SQL Server",
            kind="sql_server",
            connection_uri=None,
            metadata={"provider": "sql_server", "host": "", "database": "", "username": ""},
        )


def test_sql_server_missing_secret_does_not_leak_credentials(seeded_db):
    db = seeded_db["db"]
    ds = create_data_source(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        name="Warehouse SQL Server",
        kind="sql_server",
        connection_uri=None,
        metadata={
            "provider": "sql_server",
            "host": "warehouse.internal",
            "database": "analytics",
            "username": "reader",
            "password": "temporary-secret",
        },
    )
    metadata = json.loads(ds.metadata_json)
    metadata["secret_ref"] = "data-source-secret-00000000-0000-0000-0000-000000000000"
    ds.metadata_json = json.dumps(metadata)

    result = run_connection_test(db, ds=ds)

    assert result["status"] == "error"
    assert "temporary-secret" not in result["message"]
    assert "not available" in result["message"]


def test_sql_server_connection_failure_sanitizes_secret_and_username(seeded_db, monkeypatch):
    db = seeded_db["db"]
    ds = create_data_source(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        name="Warehouse SQL Server",
        kind="sql_server",
        connection_uri=None,
        metadata={
            "provider": "sql_server",
            "host": "warehouse.internal",
            "database": "analytics",
            "username": "reader",
            "password": "temporary-secret",
        },
    )

    def fail_with_secret(uri: str) -> dict:
        raise RuntimeError(f"failed for reader using {uri} and temporary-secret")

    monkeypatch.setattr("platform_api.services.data_source_service._test_sqlalchemy_connection", fail_with_secret)

    result = run_connection_test(db, ds=ds)

    assert result["status"] == "error"
    assert "temporary-secret" not in result["message"]
    assert "reader" not in result["message"]
    assert "****" in result["message"]


def test_sql_server_connection_smoke_uses_durable_secret(seeded_db, monkeypatch):
    db = seeded_db["db"]
    ds = create_data_source(
        db,
        tenant_id=seeded_db["tenant"].id,
        workspace_id=seeded_db["workspace"].id,
        user_id=seeded_db["user_admin"].id,
        name="Warehouse SQL Server",
        kind="sql_server",
        connection_uri=None,
        metadata={
            "provider": "sql_server",
            "host": "warehouse.internal",
            "port": 1433,
            "database": "analytics",
            "username": "reader",
            "password": "temporary-secret",
            "encrypt": True,
            "trust_server_certificate": False,
        },
    )
    captured: dict[str, str] = {}

    def succeed(uri: str) -> dict:
        captured["uri"] = uri
        return {"message": "SQL Server connection succeeded.", "details": {"driver": "pymssql"}}

    monkeypatch.setattr("platform_api.services.data_source_service._test_sqlalchemy_connection", succeed)

    result = run_connection_test(db, ds=ds)
    payload = _ds_to_dict(ds)

    assert result["status"] == "ok"
    assert "temporary-secret" in captured["uri"]
    assert "temporary-secret" not in payload["connection_uri"]
    assert "secret_ref" not in payload["metadata"]
    assert payload["metadata"]["has_secret"] is True
