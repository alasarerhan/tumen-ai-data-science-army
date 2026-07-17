"""Rate limiting middleware with X-RateLimit headers."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

def _normalize_redis_url(url):
    """Prepend the default redis scheme if a URL has only host:port/db."""
    if not url:
        return url
    for prefix in ('redis://', 'redis://' + 's' + '://', 'unix://'):
        if url.startswith(prefix):
            return url
    return 'redis://' + url


REDIS_AVAILABLE = False
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for per-client rate limiting with X-RateLimit headers."""

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        redis_url: Optional[str] = None,
        key_header: str = "X-User-Id",
        skip_paths: Optional[List[str]] = None,
        auth_paths: Optional[Dict[str, int]] = None,
        **redis_kwargs,
    ) -> None:
        super().__init__(app)
        self._rpm = requests_per_minute
        self._key_header = key_header
        self._skip_paths = set(skip_paths or ["/health", "/healthz", "/metrics", "/ready"])
        self._auth_paths = auth_paths or {
            "/v1/auth/login/dev": 10,
            "/v1/auth/refresh": 20,
            "/v1/auth/logout": 30,
            "/v1/me": 30,
            "/v1/provisioning/invites/accept": 10,
            "/v1/provisioning/tenants": 5,
            "/v1/provisioning/workspaces": 10,
            "/v1/chat/sessions/": 90,
            "/v1/artifacts": 60,
        }
        self._window_seconds = 60
        self._lock = threading.Lock()

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(_normalize_redis_url(redis_url), **redis_kwargs)
            self._in_memory: Optional[Dict[str, List[float]]] = None
            logger.info("RateLimitMiddleware connected to Redis: %s", redis_url)
        else:
            self._redis = None
            self._in_memory = {}
            if redis_url and not REDIS_AVAILABLE:
                logger.warning(
                    "Redis not available (pip install redis). "
                    "Using in-memory rate limiting (not distributed)."
                )

    def _get_client_id(self, request: Request) -> str:
        user_id = request.headers.get(self._key_header)
        if user_id:
            return f"user:{user_id}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _bucket_for_path(self, path: str) -> str:
        for auth_path in self._auth_paths:
            if path.startswith(auth_path):
                return auth_path
        return "__default__"

    def _rate_limit_key(self, client_id: str, path: str) -> str:
        return f"ratelimit:{client_id}:{self._bucket_for_path(path)}"

    def _get_rpm_for_path(self, path: str) -> int:
        for auth_path, rpm in self._auth_paths.items():
            if path.startswith(auth_path):
                return rpm
        return self._rpm

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self._skip_paths:
            return await call_next(request)

        client_id = self._get_client_id(request)
        key = self._rate_limit_key(client_id, request.url.path)
        now = time.time()
        window_start = now - self._window_seconds
        rpm = self._get_rpm_for_path(request.url.path)

        if self._redis:
            return await self._dispatch_redis(request, call_next, key, now, window_start, rpm)
        return await self._dispatch_memory(request, call_next, key, now, window_start, rpm)

    async def _dispatch_redis(
        self,
        request: Request,
        call_next: Callable,
        key: str,
        now: float,
        window_start: float,
        rpm: int,
    ) -> Response:
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self._window_seconds + 1)
        results = pipe.execute()

        current_count = results[1]
        remaining = max(0, rpm - current_count - 1)
        reset_time = int(window_start + self._window_seconds)

        if current_count >= rpm:
            self._log_limit_exceeded(key, request.url.path, rpm)
            return JSONResponse(
                content={"detail": "Rate limit exceeded. Please retry later."},
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(rpm),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(self._window_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response

    async def _dispatch_memory(
        self,
        request: Request,
        call_next: Callable,
        key: str,
        now: float,
        window_start: float,
        rpm: int,
    ) -> Response:
        with self._lock:
            assert self._in_memory is not None
            if key in self._in_memory:
                self._in_memory[key] = [t for t in self._in_memory[key] if t > window_start]
            else:
                self._in_memory[key] = []

            current_count = len(self._in_memory[key])
            remaining = max(0, rpm - current_count - 1)
            reset_time = int(window_start + self._window_seconds)

            if current_count >= rpm:
                self._log_limit_exceeded(key, request.url.path, rpm)
                return JSONResponse(
                    content={"detail": "Rate limit exceeded. Please retry later."},
                    status_code=429,
                    headers={
                        "X-RateLimit-Limit": str(rpm),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time),
                        "Retry-After": str(self._window_seconds),
                    },
                )

            self._in_memory[key].append(now)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response

    def _log_limit_exceeded(self, key: str, path: str, rpm: int) -> None:
        logger.warning("Rate limit exceeded for %s", key)
        logger.warning(
            "security_rate_limit_exceeded key=%s path=%s rpm=%s",
            key,
            path,
            rpm,
        )


__all__ = ["RateLimitMiddleware", "REDIS_AVAILABLE"]

