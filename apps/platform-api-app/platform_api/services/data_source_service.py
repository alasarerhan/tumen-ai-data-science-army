from __future__ import annotations

import importlib.util
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from platform_api.core.service_errors import NotFoundError
from platform_api.db.models import DataSource
from platform_api.db.tenant_query import TenantQuery


def _parse_uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
    return TenantQuery._parse_uuid(value, label)


def _normalize_data_source_not_found_error(exc: Exception) -> Exception:
    if getattr(exc, "status_code", None) == 404 and getattr(exc, "detail", None) == "DataSource not found":
        return NotFoundError("Data source not found")
    return exc


def list_data_sources(db: Session, *, workspace_id: uuid.UUID) -> list[DataSource]:
    return TenantQuery(db, DataSource).for_workspace(workspace_id).list()


def get_data_source(db: Session, *, ds_id: uuid.UUID, workspace_id: uuid.UUID) -> DataSource:
    """Get a data source by ID, ensuring it belongs to the specified workspace.

    Security: workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities.
    """
    parsed_ds_id = _parse_uuid(ds_id, "workspace_id")
    try:
        return TenantQuery(db, DataSource).for_workspace(workspace_id).get(parsed_ds_id)
    except Exception as exc:
        raise _normalize_data_source_not_found_error(exc) from exc


def create_data_source(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    kind: str,
    connection_uri: str,
    metadata: dict | None = None,
) -> DataSource:
    ds = DataSource(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        created_by_user_id=user_id,
        name=name,
        kind=kind,
        connection_uri=connection_uri,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(ds)
    db.flush()
    return ds


def update_data_source(
    db: Session,
    *,
    ds: DataSource,
    name: str | None = None,
    kind: str | None = None,
    connection_uri: str | None = None,
    metadata: dict | None = None,
) -> DataSource:
    if name is not None:
        ds.name = name
    if kind is not None:
        ds.kind = kind
    if connection_uri is not None:
        ds.connection_uri = connection_uri
    if metadata is not None:
        ds.metadata_json = json.dumps(metadata)
    ds.updated_at = datetime.now(UTC)
    db.add(ds)
    db.flush()
    return ds


def test_data_source_connection(
    db: Session,
    *,
    ds: DataSource,
) -> dict:
    parsed = urlparse(ds.connection_uri)
    scheme = parsed.scheme.lower()

    try:
        if scheme == "file":
            result = _test_local_path(parsed)
        elif scheme == "mcp":
            result = _test_mcp_module(parsed)
        elif scheme == "sqlite":
            result = _test_sqlite_connection(parsed)
        elif scheme == "duckdb":
            result = _test_duckdb_connection(parsed)
        else:
            result = _test_sqlalchemy_connection(ds.connection_uri)
        status = "ok"
    except Exception as exc:
        result = {
            "status": "error",
            "message": str(exc),
        }
        status = "error"

    metadata = json.loads(ds.metadata_json) if ds.metadata_json else {}
    metadata["connection_test"] = {
        **result,
        "status": status,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    ds.metadata_json = json.dumps(metadata)
    ds.updated_at = datetime.now(UTC)
    db.add(ds)
    db.flush()
    return metadata["connection_test"]


def _test_local_path(parsed) -> dict:
    raw_path = parsed.path or ""
    if parsed.netloc and not raw_path.startswith("/"):
        raw_path = f"/{raw_path}"
    if raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    path = Path(raw_path)
    if not path.exists():
        raise ValueError(f"Path not found: {path}")
    kind = "directory" if path.is_dir() else "file"
    return {
        "message": f"Local {kind} is reachable.",
        "details": {"path": str(path), "kind": kind},
    }


def _test_mcp_module(parsed) -> dict:
    module_name = (parsed.netloc or parsed.path.lstrip("/")).strip()
    if not module_name:
        raise ValueError("MCP module path is required")
    if importlib.util.find_spec(module_name) is None:
        raise ValueError(f"MCP module not found: {module_name}")
    return {
        "message": f"MCP module '{module_name}' is importable.",
        "details": {"module": module_name},
    }


def _test_sqlite_connection(parsed) -> dict:
    raw_path = parsed.path or ""
    if raw_path in {"", "/:memory:"}:
        conn = sqlite3.connect(":memory:")
        conn.execute("SELECT 1")
        conn.close()
        return {"message": "SQLite in-memory database is reachable.", "details": {"database": ":memory:"}}

    if raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    db_path = Path(raw_path)
    if not db_path.exists():
        raise ValueError(f"SQLite database not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("SELECT 1")
    finally:
        conn.close()
    return {"message": "SQLite database connection succeeded.", "details": {"database": str(db_path)}}


def _test_duckdb_connection(parsed) -> dict:
    try:
        import duckdb
    except ImportError as exc:
        raise ValueError("duckdb package is not installed") from exc

    raw_path = parsed.path or ""
    if raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    db_path = Path(raw_path)
    if raw_path and not db_path.exists():
        raise ValueError(f"DuckDB database not found: {db_path}")
    conn = duckdb.connect(database=str(db_path) if raw_path else ":memory:", read_only=bool(raw_path))
    try:
        conn.execute("SELECT 1").fetchall()
    finally:
        conn.close()
    return {"message": "DuckDB connection succeeded.", "details": {"database": str(db_path) if raw_path else ":memory:"}}


def _test_sqlalchemy_connection(connection_uri: str) -> dict:
    engine = create_engine(connection_uri, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        engine.dispose()
    return {"message": "Connection test succeeded.", "details": {"dialect": engine.dialect.name}}


def delete_data_source(db: Session, *, ds: DataSource) -> None:
    db.delete(ds)
    db.flush()
