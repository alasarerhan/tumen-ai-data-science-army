"""Optimistic locking utilities using ETag/If-Match headers.

Prevents lost updates when multiple clients concurrently modify the same resource.
Returns 409 Conflict when the resource has been modified since the client read it.

Design
------
* **ETag generation**: Hash of resource ID + version + updated_at
* **If-Match validation**: Client sends ETag from previous GET
* **409 Conflict**: When ETag doesn't match current state

Usage
-----
::

    from platform_api.core.etag import compute_etag, validate_etag

    @router.get("/{resource_id}")
    async def get_resource(resource_id: str):
        resource = get_resource_from_db(resource_id)
        etag = compute_etag(resource)
        return {"data": resource_to_dict(resource), "_etag": etag}

    @router.put("/{resource_id}")
    async def update_resource(
        resource_id: str,
        if_match: str = Header(...),
    ):
        resource = get_resource_from_db(resource_id)
        validate_etag(resource, if_match)  # Raises 409 if mismatch
        # Proceed with update

Best Practices Reference:
https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag
https://datatracker.ietf.org/doc/html/rfc7232
"""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import HTTPException


def compute_etag(record: Any, include_fields: list[str] | None = None) -> str:
    """Compute an ETag for a database record.

    Uses record ID, version (if available), and updated_at timestamp.
    Returns a weak ETag (prefixed with W/) suitable for conditional requests.

    Parameters
    ----------
    record : Any
        Database model instance with id, version, and updated_at attributes.
    include_fields : list[str] | None
        Additional fields to include in the hash.

    Returns
    -------
    str
        ETag value (e.g., "W/abc123").
    """
    parts = [str(getattr(record, "id", ""))]

    if hasattr(record, "version"):
        parts.append(str(record.version))

    if hasattr(record, "updated_at") and record.updated_at:
        parts.append(record.updated_at.isoformat())

    if include_fields:
        for field in include_fields:
            value = getattr(record, field, None)
            if value is not None:
                parts.append(str(value))

    data = ":".join(parts)
    hash_value = hashlib.md5(data.encode()).hexdigest()[:16]
    return f'W/"{hash_value}"'


def validate_etag(record: Any, if_match: str, include_fields: list[str] | None = None) -> None:
    """Validate If-Match header against current record state.

    Raises HTTPException with 409 Conflict if the ETag doesn't match.

    Parameters
    ----------
    record : Any
        Database model instance.
    if_match : str
        ETag value from If-Match header.
    include_fields : list[str] | None
        Additional fields to include in the hash.

    Raises
    ------
    HTTPException
        409 Conflict if ETag doesn't match.
    """
    current_etag = compute_etag(record, include_fields)

    if if_match != current_etag:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Resource has been modified by another client",
                "current_etag": current_etag,
                "provided_etag": if_match,
            },
        )


__all__ = [
    "compute_etag",
    "validate_etag",
]
