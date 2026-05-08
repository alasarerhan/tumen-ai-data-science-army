from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import delete

from platform_api.core.config import settings
from platform_api.db.models import TenantQuotaEvent
from platform_api.services.quota_service import enforce_tenant_write_quota


def test_quota_is_tracked_in_db_and_enforced(seeded_db):
    db = seeded_db["db"]
    tenant_id = str(seeded_db["tenant"].id)
    prev_quota = settings.tenant_write_quota_per_minute

    try:
        settings.tenant_write_quota_per_minute = 2
        db.execute(delete(TenantQuotaEvent))
        db.flush()

        enforce_tenant_write_quota(db, tenant_id)
        enforce_tenant_write_quota(db, tenant_id)
        with pytest.raises(HTTPException) as exc:
            enforce_tenant_write_quota(db, tenant_id)

        assert exc.value.status_code == 429
    finally:
        settings.tenant_write_quota_per_minute = prev_quota
