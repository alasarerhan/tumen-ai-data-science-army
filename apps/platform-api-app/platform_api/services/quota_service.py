from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import TenantQuotaEvent
from platform_api.core.service_errors import RateLimitExceededError, ValidationError


def _parse_tenant_id(tenant_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(tenant_id)
    except ValueError as exc:
        raise ValidationError("Invalid tenant_id") from exc


def _lock_tenant_quota_counter(db: Session, tenant_id: uuid.UUID) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:tenant_key))"),
        {"tenant_key": str(tenant_id)},
    )


def enforce_tenant_write_quota(db: Session, tenant_id: str) -> None:
    tenant_uuid = _parse_tenant_id(tenant_id)
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=1)

    # Serialize quota checks per tenant across all replicas.
    _lock_tenant_quota_counter(db, tenant_uuid)

    db.execute(
        delete(TenantQuotaEvent).where(
            TenantQuotaEvent.tenant_id == tenant_uuid,
            TenantQuotaEvent.created_at < window_start,
        )
    )

    current_count = db.execute(
        select(func.count(TenantQuotaEvent.id)).where(
            TenantQuotaEvent.tenant_id == tenant_uuid,
            TenantQuotaEvent.created_at >= window_start,
        )
    ).scalar_one()

    if int(current_count or 0) >= settings.tenant_write_quota_per_minute:
        raise RateLimitExceededError("Tenant write quota exceeded")

    db.add(TenantQuotaEvent(tenant_id=tenant_uuid, created_at=now))
    db.flush()
