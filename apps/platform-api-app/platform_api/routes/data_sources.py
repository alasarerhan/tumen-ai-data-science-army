from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_workspace_member
from platform_api.db.models import DataSource
from platform_api.db.session import get_db
from platform_api.services.data_source_service import (
    create_data_source,
    delete_data_source,
    get_data_source,
    list_data_sources,
    test_data_source_connection,
    update_data_source,
)

router = APIRouter(prefix="/v1/data-sources", tags=["data-sources"])


ALLOWED_CONNECTION_SCHEMES = [
    "postgresql://",
    "postgres://",
    "mysql://",
    "mariadb://",
    "sqlite:///",
    "duckdb:///",
    "file:///",
    "mcp://",
    "snowflake://",
    "bigquery://",
    "redshift://",
    "oracle://",
    "mssql://",
    "mssql+pymssql://",
    "mssql+pyodbc://",
    "clickhouse://",
]


def _validate_connection_uri(uri: str) -> str:
    """Validate connection URI for security.
    
    SECURITY: Prevents SSRF and credential exfiltration attacks.
    Only allows known database connection schemes.
    """
    if not uri or not isinstance(uri, str):
        raise ValueError("Connection URI is required")
    
    uri_lower = uri.lower().strip()
    
    if not any(uri_lower.startswith(scheme) for scheme in ALLOWED_CONNECTION_SCHEMES):
        raise ValueError(
            f"Connection URI scheme not allowed. "
            f"Allowed schemes: {', '.join(s.replace('://', '') for s in ALLOWED_CONNECTION_SCHEMES)}"
        )
    
    return uri


def _mask_connection_uri(uri: str) -> str:
    """Mask credentials in connection URI for safe display.

    Security: Prevents accidental exposure of passwords in API responses.
    Handles common URI formats: postgresql://user:pass@host/db
    """
    if not uri:
        return uri
    pattern = r"(://[^:]+:)([^@]+)(@)"
    return re.sub(pattern, r"\1****\3", uri)


def _ds_to_dict(ds: DataSource) -> dict:
    metadata = json.loads(ds.metadata_json) if ds.metadata_json else {}
    safe_metadata = _safe_metadata(metadata)
    return {
        "id": str(ds.id),
        "workspace_id": str(ds.workspace_id),
        "tenant_id": str(ds.tenant_id),
        "name": ds.name,
        "kind": ds.kind,
        "connection_uri": _mask_connection_uri(ds.connection_uri),
        "metadata": safe_metadata,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
        "updated_at": ds.updated_at.isoformat() if ds.updated_at else None,
    }


def _safe_metadata(metadata: dict) -> dict:
    safe = dict(metadata)
    safe.pop("password", None)
    safe.pop("secret_value", None)
    if "secret_ref" in safe:
        safe["has_secret"] = True
        safe.pop("secret_ref", None)
    return safe


@router.get("")
async def list_ds(
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    items = list_data_sources(db, workspace_id=workspace.id)
    return {"items": [_ds_to_dict(ds) for ds in items]}


class CreateDataSourceRequest(BaseModel):
    workspace_id: str
    name: str
    kind: str
    connection_uri: str | None = None
    metadata: dict = Field(default_factory=dict)
    
    @field_validator('connection_uri')
    @classmethod
    def validate_connection_uri(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_connection_uri(v)


@router.post("", status_code=201)
async def create_ds(
    body: CreateDataSourceRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    user = context["user"]
    try:
        ds = create_data_source(
            db,
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            user_id=user.id,
            name=body.name,
            kind=body.kind,
            connection_uri=body.connection_uri,
            metadata=body.metadata or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(ds)
    return _ds_to_dict(ds)


class UpdateDataSourceRequest(BaseModel):
    workspace_id: str
    name: str | None = None
    kind: str | None = None
    connection_uri: str | None = None
    metadata: dict | None = None
    
    @field_validator('connection_uri')
    @classmethod
    def validate_connection_uri(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_connection_uri(v)


@router.put("/{ds_id}")
async def update_ds(
    ds_id: str,
    body: UpdateDataSourceRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    try:
        ds_uuid = uuid.UUID(ds_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ds_id") from exc
    ds = get_data_source(db, ds_id=ds_uuid, workspace_id=workspace.id)
    try:
        ds = update_data_source(
            db,
            ds=ds,
            name=body.name,
            kind=body.kind,
            connection_uri=body.connection_uri,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(ds)
    return _ds_to_dict(ds)


@router.delete("/{ds_id}", status_code=204)
async def delete_ds(
    ds_id: str,
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> None:
    workspace = context["workspace"]
    try:
        ds_uuid = uuid.UUID(ds_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ds_id") from exc
    ds = get_data_source(db, ds_id=ds_uuid, workspace_id=workspace.id)
    delete_data_source(db, ds=ds)
    db.commit()


class TestConnectionRequest(BaseModel):
    workspace_id: str


@router.post("/{ds_id}/test")
async def test_connection(
    ds_id: str,
    body: TestConnectionRequest,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    try:
        ds_uuid = uuid.UUID(ds_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid ds_id") from exc
    ds = get_data_source(db, ds_id=ds_uuid, workspace_id=workspace.id)
    result = test_data_source_connection(db, ds=ds)
    db.commit()
    return result
