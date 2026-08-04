"""Request body size limit middleware.

Prevents denial-of-service attacks via large request bodies.
Returns 413 Payload Too Large when the request body exceeds the limit.

Design
------
* **Configurable limit**: Default 10MB, configurable via environment
* **Per-route override**: Allow specific routes to have different limits
* **413 response**: Proper HTTP status code with clear error message

Best Practices Reference:
https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/413
https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size.

    Parameters
    ----------
    app : ASGIApp
        The FastAPI application.
    max_body_bytes : int
        Maximum request body size in bytes (default: 10MB).
    skip_paths : list[str] | None
        Paths to skip size limit checks (e.g., health checks).
    route_limits : list[tuple[str, int]] | None
        Per-route limits as list of (path_prefix, max_bytes) tuples.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
        skip_paths: list[str] | None = None,
        route_limits: list[tuple[str, int]] | None = None,
    ) -> None:
        super().__init__(app)
        self._max_body_bytes = max_body_bytes
        self._skip_paths = set(skip_paths or ["/health", "/healthz", "/metrics", "/ready"])
        self._route_limits = route_limits or []

    def _get_limit_for_path(self, path: str) -> int:
        for prefix, limit in self._route_limits:
            if path.startswith(prefix):
                return limit
        return self._max_body_bytes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self._skip_paths:
            return await call_next(request)

        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                limit = self._get_limit_for_path(request.url.path)
                if length > limit:
                    logger.warning(
                        "Request body too large: %d bytes (limit: %d) for %s",
                        length,
                        limit,
                        request.url.path,
                    )
                    return JSONResponse(
                        content={
                            "detail": f"Request body too large. Maximum allowed: {limit} bytes",
                            "max_bytes": limit,
                            "received_bytes": length,
                        },
                        status_code=413,
                    )
            except ValueError:
                pass

        return await call_next(request)


__all__ = [
    "RequestSizeLimitMiddleware",
]
