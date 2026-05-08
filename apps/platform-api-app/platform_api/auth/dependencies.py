from __future__ import annotations

import ipaddress
import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from platform_api.auth.models import Principal
from platform_api.core.config import settings

logger = logging.getLogger(__name__)


bearer_scheme = HTTPBearer(auto_error=False)


def _normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    normalized = email.strip().lower()
    return normalized or None


def _enforce_oidc_identity_requirements(claims: dict) -> str:
    email = _normalize_email(claims.get("email"))
    if not email:
        raise HTTPException(status_code=401, detail="Token missing verified email")

    if settings.oidc_require_verified_email and claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Token email is not verified")

    allowed_domains = {
        domain.strip().lower()
        for domain in settings.oidc_allowed_email_domains.split(",")
        if domain.strip()
    }
    if allowed_domains:
        domain = email.rsplit("@", 1)[-1]
        if domain not in allowed_domains:
            raise HTTPException(status_code=403, detail="Email domain is not allowed")

    return email


def _is_loopback_request(request: Request) -> bool:
    client = request.client
    if client is None or not client.host:
        return False
    try:
        return ipaddress.ip_address(client.host).is_loopback
    except ValueError:
        return client.host.lower() == "localhost"


def _require_dev_mode_request(request: Request) -> None:
    if not settings.is_local_profile():
        raise HTTPException(
            status_code=503,
            detail="AUTH_MODE=dev is only allowed when DEPLOYMENT_PROFILE=local. "
                   "This is a security measure to prevent authentication bypass in production.",
        )
    if not settings.dev_auth_token:
        raise HTTPException(
            status_code=503,
            detail="DEV_AUTH_TOKEN must be configured before development authentication can be used.",
        )
    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=403,
            detail="Development authentication is restricted to loopback requests.",
        )


@lru_cache(maxsize=8)
def _build_oidc_verifier(issuer: str, audience: str, jwks_url: str):
    from platform_api.auth.oidc import OIDCConfig, OIDCVerifier

    return OIDCVerifier(
        OIDCConfig(
            issuer=issuer,
            audience=audience,
            jwks_url=jwks_url,
        )
    )


def reset_oidc_verifier_cache() -> None:
    _build_oidc_verifier.cache_clear()


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    token = request.cookies.get("access_token")
    auth_source = "cookie"

    if not token and credentials is not None and credentials.credentials:
        token = credentials.credentials
        auth_source = "bearer"

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    request.state.auth_source = auth_source

    if settings.auth_mode == "dev":
        _require_dev_mode_request(request)
        if token != settings.dev_auth_token:
            raise HTTPException(status_code=401, detail="Invalid dev token")
        logger.warning(
            "DEV AUTH MODE ACTIVE: Using development authentication. "
            "This should NEVER be enabled in production."
        )
        return Principal(
            sub="dev-user",
            email=_normalize_email(settings.dev_auth_email),
            claims={"mode": "dev", "auth_source": auth_source},
        )

    if settings.auth_mode != "oidc":
        raise HTTPException(status_code=500, detail="Unsupported AUTH_MODE")

    if not settings.oidc_jwks_url:
        raise HTTPException(status_code=500, detail="OIDC_JWKS_URL is required for oidc mode")

    verifier = _build_oidc_verifier(
        settings.oidc_issuer,
        settings.oidc_audience,
        settings.oidc_jwks_url,
    )

    try:
        claims = await verifier.verify(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing 'sub'")

    email = _enforce_oidc_identity_requirements(claims)
    return Principal(sub=str(sub), email=email, claims=claims)
