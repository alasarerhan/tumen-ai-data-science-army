from __future__ import annotations

import base64
import hashlib
import uuid

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import DataSourceSecret

SECRET_REF_PREFIX = "data-source-secret-"


def put_data_source_secret(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    value: str,
    purpose: str,
    created_by_user_id: uuid.UUID | None = None,
    data_source_id: uuid.UUID | None = None,
) -> str:
    """Persist secret material behind an opaque reference.

    The API contract exposes only the returned reference marker through masked
    metadata. The encrypted payload never leaves the backend boundary.
    """
    secret = DataSourceSecret(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        data_source_id=data_source_id,
        purpose=purpose,
        encrypted_value=_encrypt(value),
        created_by_user_id=created_by_user_id,
    )
    db.add(secret)
    db.flush()
    return f"{SECRET_REF_PREFIX}{secret.id}"


def get_data_source_secret(
    db: Session,
    *,
    ref: str | None,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> str | None:
    secret_id = _parse_secret_ref(ref)
    if secret_id is None:
        return None
    secret = (
        db.query(DataSourceSecret)
        .filter(
            DataSourceSecret.id == secret_id,
            DataSourceSecret.tenant_id == tenant_id,
            DataSourceSecret.workspace_id == workspace_id,
        )
        .one_or_none()
    )
    if secret is None:
        return None
    return _decrypt(secret.encrypted_value)


def _parse_secret_ref(ref: str | None) -> uuid.UUID | None:
    if not ref or not ref.startswith(SECRET_REF_PREFIX):
        return None
    try:
        return uuid.UUID(ref.removeprefix(SECRET_REF_PREFIX))
    except ValueError:
        return None


def _fernet() -> Fernet:
    key_material = settings.data_source_secret_key.strip()
    if not key_material:
        if settings.is_production_profile():
            raise RuntimeError("DATA_SOURCE_SECRET_KEY is required before storing data source secrets")
        key_material = f"local-dev:{settings.database_url}:{settings.deployment_profile}"
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
