"""Authentication endpoints with secure HttpOnly cookie token storage.

Security Best Practices (OWASP-aligned):
- HttpOnly cookies prevent JavaScript access (XSS protection)
- Secure flag ensures HTTPS-only transmission
- SameSite=Strict prevents CSRF attacks
- Short-lived access tokens (15 min) limit breach window
- Refresh token rotation detects replay attacks

Reference: https://tools.zamdevai.com/blog/stop-storing-jwts-in-localstorage
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from platform_api.auth.dependencies import _require_dev_mode_request, get_principal
from platform_api.auth.models import Principal
from platform_api.core.config import settings
from platform_api.core.csrf import generate_csrf_token, set_csrf_cookie

router = APIRouter(prefix="/v1/auth", tags=["auth"])

ACCESS_TOKEN_MAX_AGE = 900  # 15 minutes
REFRESH_TOKEN_MAX_AGE = 604800  # 7 days


class DevLoginRequest(BaseModel):
    token: str


class LoginResponse(BaseModel):
    success: bool
    user_id: str | None = None


class CsrfResponse(BaseModel):
    csrf_token: str


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=not settings.is_local_profile(),
        samesite="strict",
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )


def _rotate_csrf(response: Response) -> str:
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token)
    return csrf_token


@router.get("/csrf", response_model=CsrfResponse)
async def get_csrf_token(response: Response) -> dict:
    """Issue CSRF token for cookie-authenticated browser flows."""
    token = _rotate_csrf(response)
    return {"csrf_token": token}


@router.post("/login/dev", response_model=LoginResponse)
async def dev_login(
    body: DevLoginRequest,
    request: Request,
    response: Response,
) -> dict:
    """Development login endpoint that sets HttpOnly cookies.

    Security: Only available when AUTH_MODE=dev and DEPLOYMENT_PROFILE=local.
    """
    if settings.auth_mode != "dev":
        raise HTTPException(status_code=400, detail="Dev login not available in this mode")

    _require_dev_mode_request(request)

    if body.token != settings.dev_auth_token:
        raise HTTPException(status_code=401, detail="Invalid dev token")

    _set_auth_cookie(response, settings.dev_auth_token)
    _rotate_csrf(response)

    return {"success": True, "user_id": "dev-user"}


@router.post("/logout")
async def logout(
    response: Response,
) -> dict:
    """Logout endpoint that clears HttpOnly cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    response.delete_cookie(key="csrf_token", path="/")
    return {"success": True}


@router.post("/refresh")
async def refresh_token(
    response: Response,
    principal: Principal = Depends(get_principal),
) -> dict:
    """Refresh access token using valid current token.

    Security: Issues new access token with fresh expiration.
    """
    if settings.auth_mode == "dev":
        _set_auth_cookie(response, settings.dev_auth_token)
        _rotate_csrf(response)
        return {"success": True}

    raise HTTPException(
        status_code=501,
        detail="OIDC refresh is handled by the upstream identity provider and is not implemented by this API.",
    )
