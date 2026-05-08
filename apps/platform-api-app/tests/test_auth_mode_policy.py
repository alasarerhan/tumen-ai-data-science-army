from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request
from unittest.mock import AsyncMock, patch
import sys
import types

from platform_api.auth.dependencies import get_principal, reset_oidc_verifier_cache
from platform_api.core.config import settings


def _request_with_cookies(cookies: dict[str, str] | None = None) -> Request:
    cookie_header = ""
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"cookie", cookie_header.encode())] if cookie_header else [],
        "client": ("127.0.0.1", 8000),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_dev_auth_is_blocked_in_release_profile():
    prev_mode = settings.auth_mode
    prev_profile = settings.deployment_profile
    prev_dev_token = settings.dev_auth_token
    try:
        settings.auth_mode = "dev"
        settings.deployment_profile = "release"
        settings.dev_auth_token = "test-dev-token"
        with pytest.raises(HTTPException) as exc:
            await get_principal(
                request=_request_with_cookies(),
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-dev-token"),
            )
        assert exc.value.status_code == 503
    finally:
        settings.auth_mode = prev_mode
        settings.deployment_profile = prev_profile
        settings.dev_auth_token = prev_dev_token


@pytest.mark.asyncio
async def test_dev_auth_works_only_in_local_profile():
    prev_mode = settings.auth_mode
    prev_profile = settings.deployment_profile
    prev_dev_token = settings.dev_auth_token
    prev_dev_email = settings.dev_auth_email
    try:
        settings.auth_mode = "dev"
        settings.deployment_profile = "local"
        settings.dev_auth_token = "test-dev-token"
        settings.dev_auth_email = "local@test.dev"
        principal = await get_principal(
            request=_request_with_cookies({"access_token": "test-dev-token"}),
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-dev-token"),
        )
        assert principal.sub == "dev-user"
        assert principal.email == "local@test.dev"
    finally:
        settings.auth_mode = prev_mode
        settings.deployment_profile = prev_profile
        settings.dev_auth_token = prev_dev_token
        settings.dev_auth_email = prev_dev_email


@pytest.mark.asyncio
async def test_cookie_token_is_preferred_over_bearer_when_present():
    prev_mode = settings.auth_mode
    prev_profile = settings.deployment_profile
    prev_dev_token = settings.dev_auth_token
    try:
        settings.auth_mode = "dev"
        settings.deployment_profile = "local"
        settings.dev_auth_token = "cookie-token"
        principal = await get_principal(
            request=_request_with_cookies({"access_token": "cookie-token"}),
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"),
        )
        assert principal.sub == "dev-user"
    finally:
        settings.auth_mode = prev_mode
        settings.deployment_profile = prev_profile
        settings.dev_auth_token = prev_dev_token


@pytest.mark.asyncio
async def test_oidc_requires_verified_email_claim():
    prev_mode = settings.auth_mode
    prev_jwks = settings.oidc_jwks_url
    prev_verified = settings.oidc_require_verified_email
    prev_module = sys.modules.get("platform_api.auth.oidc")
    try:
        settings.auth_mode = "oidc"
        settings.oidc_jwks_url = "https://accounts.google.com/.well-known/jwks.json"
        settings.oidc_require_verified_email = True
        fake_module = types.ModuleType("platform_api.auth.oidc")

        class FakeOIDCConfig:
            def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
                self.issuer = issuer
                self.audience = audience
                self.jwks_url = jwks_url

        class FakeOIDCVerifier:
            def __init__(self, config: FakeOIDCConfig) -> None:
                self.config = config

            verify = AsyncMock(return_value={
                "sub": "oidc-user",
                "email": "user@example.com",
                "email_verified": False,
            })

        fake_module.OIDCConfig = FakeOIDCConfig
        fake_module.OIDCVerifier = FakeOIDCVerifier
        sys.modules["platform_api.auth.oidc"] = fake_module
        reset_oidc_verifier_cache()

        with pytest.raises(HTTPException, match=r"not verified") as exc_info:
            await get_principal(
                request=_request_with_cookies(),
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            )
        assert exc_info.value.status_code == 401
    finally:
        settings.auth_mode = prev_mode
        settings.oidc_jwks_url = prev_jwks
        settings.oidc_require_verified_email = prev_verified
        reset_oidc_verifier_cache()
        if prev_module is None:
            sys.modules.pop("platform_api.auth.oidc", None)
        else:
            sys.modules["platform_api.auth.oidc"] = prev_module


@pytest.mark.asyncio
async def test_oidc_enforces_allowed_email_domains():
    prev_mode = settings.auth_mode
    prev_jwks = settings.oidc_jwks_url
    prev_domains = settings.oidc_allowed_email_domains
    prev_module = sys.modules.get("platform_api.auth.oidc")
    try:
        settings.auth_mode = "oidc"
        settings.oidc_jwks_url = "https://accounts.google.com/.well-known/jwks.json"
        settings.oidc_allowed_email_domains = "corp.example"
        fake_module = types.ModuleType("platform_api.auth.oidc")

        class FakeOIDCConfig:
            def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
                self.issuer = issuer
                self.audience = audience
                self.jwks_url = jwks_url

        class FakeOIDCVerifier:
            def __init__(self, config: FakeOIDCConfig) -> None:
                self.config = config

            verify = AsyncMock(return_value={
                "sub": "oidc-user",
                "email": "user@gmail.com",
                "email_verified": True,
            })

        fake_module.OIDCConfig = FakeOIDCConfig
        fake_module.OIDCVerifier = FakeOIDCVerifier
        sys.modules["platform_api.auth.oidc"] = fake_module
        reset_oidc_verifier_cache()

        with pytest.raises(HTTPException, match=r"not allowed") as exc_info:
            await get_principal(
                request=_request_with_cookies(),
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="token"),
            )
        assert exc_info.value.status_code == 403
    finally:
        settings.auth_mode = prev_mode
        settings.oidc_jwks_url = prev_jwks
        settings.oidc_allowed_email_domains = prev_domains
        reset_oidc_verifier_cache()
        if prev_module is None:
            sys.modules.pop("platform_api.auth.oidc", None)
        else:
            sys.modules["platform_api.auth.oidc"] = prev_module
