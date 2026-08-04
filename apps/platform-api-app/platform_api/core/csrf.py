from __future__ import annotations

import logging
import secrets
from collections.abc import Iterable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from platform_api.core.config import settings

logger = logging.getLogger(__name__)

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def generate_csrf_token() -> str:
    """Generate a high-entropy CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF cookie used by double-submit protection."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=not settings.is_local_profile(),
        samesite="strict",
        path="/",
    )


def _has_bearer_auth(request: Request) -> bool:
    auth_header = request.headers.get("authorization", "")
    return auth_header.lower().startswith("bearer ")


def _is_cookie_auth_request(request: Request) -> bool:
    return bool(request.cookies.get("access_token")) and not _has_bearer_auth(request)


def _is_csrf_exempt_path(path: str, exempt_paths: Iterable[str]) -> bool:
    return any(path.startswith(prefix) for prefix in exempt_paths)


def validate_csrf_request(request: Request) -> None:
    """Validate CSRF token for cookie-authenticated mutation requests."""
    if not settings.csrf_enabled:
        return

    if request.method.upper() not in UNSAFE_METHODS:
        return

    exempt_paths = [p.strip() for p in settings.csrf_exempt_paths.split(",") if p.strip()]
    if _is_csrf_exempt_path(request.url.path, exempt_paths):
        return

    if not _is_cookie_auth_request(request):
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="CSRF token required")
    if cookie_token != header_token:
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


class CsrfProtectionMiddleware(BaseHTTPMiddleware):
    """Enforce CSRF for unsafe methods when cookie authentication is used."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        try:
            validate_csrf_request(request)
        except HTTPException as exc:
            logger.warning(
                "csrf_rejected method=%s path=%s detail=%s",
                request.method,
                request.url.path,
                exc.detail,
            )
            return JSONResponse(
                content={"detail": exc.detail},
                status_code=exc.status_code,
            )
        return await call_next(request)
