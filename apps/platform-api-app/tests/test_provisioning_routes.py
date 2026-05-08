from __future__ import annotations

import pytest
from fastapi import HTTPException

from platform_api.auth.models import Principal
from platform_api.core.config import settings
from platform_api.routes.provisioning import create_tenant
from platform_api.schemas.provisioning import CreateTenantRequest


@pytest.mark.asyncio
async def test_create_tenant_is_disabled_by_default(db_session) -> None:
    prev_value = settings.allow_self_service_tenant_creation
    try:
        settings.allow_self_service_tenant_creation = False
        with pytest.raises(HTTPException, match=r"disabled") as exc_info:
            await create_tenant(
                payload=CreateTenantRequest(name="Locked Down"),
                principal=Principal(
                    sub="sub|tenant-creator",
                    email="creator@corp.example",
                    claims={"email_verified": True},
                ),
                db=db_session,
            )
        assert exc_info.value.status_code == 403
    finally:
        settings.allow_self_service_tenant_creation = prev_value
