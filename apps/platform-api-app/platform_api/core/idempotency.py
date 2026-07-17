"""Idempotency middleware for API requests.

Provides request deduplication using idempotency keys stored in Redis.
Prevents duplicate resource creation on client retries.

Design
------
* **Idempotency key**: Client sends `X-Idempotency-Key` header
* **Response caching**: Successful responses cached for 24 hours (configurable)
* **Concurrent requests**: Returns 409 Conflict if same key is in-flight
* **Redis-backed**: Distributed across multiple API replicas

Usage
-----
::

    from platform_api.core.idempotency import IdempotencyMiddleware

    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware, redis_url="redis://localhost:6379/0")

Client sends::

    POST /v1/sessions
    X-Idempotency-Key: client-generated-uuid
    { "title": "New chat" }

On retry with same key, returns cached response without re-executing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

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


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware for request idempotency using Redis.

    Caches successful POST/PUT/PATCH responses keyed by idempotency key.
    Prevents duplicate resource creation on client retries.

    Parameters
    ----------
    app : ASGIApp
        The FastAPI application.
    redis_url : str | None
        Redis connection URL. If None, uses in-memory cache (not distributed).
    key_header : str
        Header name for idempotency key (default: "X-Idempotency-Key").
    ttl_seconds : int
        How long to cache responses (default: 86400 = 24 hours).
    in_flight_ttl_seconds : int
        How long to track in-flight requests (default: 300 = 5 minutes).
    skip_paths : list[str] | None
        Paths to skip idempotency checks (e.g., health checks).
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_url: Optional[str] = None,
        key_header: str = "X-Idempotency-Key",
        ttl_seconds: int = 86400,
        in_flight_ttl_seconds: int = 300,
        skip_paths: Optional[list[str]] = None,
        **redis_kwargs,
    ) -> None:
        super().__init__(app)
        self._key_header = key_header
        self._ttl = ttl_seconds
        self._in_flight_ttl = in_flight_ttl_seconds
        self._skip_paths = set(skip_paths or ["/health", "/healthz", "/ready", "/metrics"])
        self._lock = threading.Lock()

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(
                _normalize_redis_url(redis_url), **redis_kwargs
            )
            self._in_memory_cache: Optional[Dict] = None
            logger.info("IdempotencyMiddleware connected to Redis: %s", redis_url)
        else:
            self._redis = None
            self._in_memory_cache: Dict[str, Any] = {}
            self._in_flight: Dict[str, float] = {}
            if redis_url and not REDIS_AVAILABLE:
                logger.warning(
                    "Redis not available (pip install redis). "
                    "Using in-memory idempotency cache (not distributed)."
                )

    def _cache_key(self, idempotency_key: str, request_hash: str) -> str:
        return f"idempotency:{idempotency_key}:{request_hash}"

    def _in_flight_key(self, idempotency_key: str) -> str:
        return f"idempotency:inflight:{idempotency_key}"

    def _request_hash(self, request: Request, body: bytes) -> str:
        method = request.method
        path = request.url.path
        query = str(request.query_params)
        return hashlib.sha256(f"{method}:{path}:{query}:{body[:1024]}".encode()).hexdigest()[:16]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self._skip_paths:
            return await call_next(request)

        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)

        idempotency_key = request.headers.get(self._key_header)
        if not idempotency_key:
            return await call_next(request)

        body = await request.body()
        request_hash = self._request_hash(request, body)
        cache_key = self._cache_key(idempotency_key, request_hash)
        in_flight_key = self._in_flight_key(idempotency_key)

        if self._redis:
            cached = self._redis.get(cache_key)
            if cached:
                logger.debug("Returning cached response for idempotency key: %s", idempotency_key)
                cached_data = json.loads(cached)
                return JSONResponse(
                    content=cached_data["body"],
                    status_code=cached_data["status_code"],
                    headers=cached_data.get("headers", {}),
                )

            in_flight = self._redis.get(in_flight_key)
            if in_flight:
                logger.warning("Concurrent request with same idempotency key: %s", idempotency_key)
                return JSONResponse(
                    content={
                        "detail": "Request with same idempotency key is already being processed",
                        "idempotency_key": idempotency_key,
                    },
                    status_code=409,
                )

            self._redis.setex(in_flight_key, self._in_flight_ttl, "1")
        else:
            with self._lock:
                if cache_key in self._in_memory_cache:
                    cached_data = self._in_memory_cache[cache_key]
                    logger.debug("Returning cached response for idempotency key: %s", idempotency_key)
                    return JSONResponse(
                        content=cached_data["body"],
                        status_code=cached_data["status_code"],
                        headers=cached_data.get("headers", {}),
                    )

                if idempotency_key in self._in_flight:
                    if time.time() - self._in_flight[idempotency_key] < self._in_flight_ttl:
                        logger.warning("Concurrent request with same idempotency key: %s", idempotency_key)
                        return JSONResponse(
                            content={
                                "detail": "Request with same idempotency key is already being processed",
                                "idempotency_key": idempotency_key,
                            },
                            status_code=409,
                        )

                self._in_flight[idempotency_key] = time.time()

        response = await call_next(request)

        if self._redis:
            self._redis.delete(in_flight_key)
        else:
            with self._lock:
                self._in_flight.pop(idempotency_key, None)

        if 200 <= response.status_code < 300:
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            try:
                body_json = json.loads(response_body)
            except json.JSONDecodeError:
                body_json = {"raw": response_body.decode("utf-8", errors="replace")}

            cache_data = {
                "body": body_json,
                "status_code": response.status_code,
                "headers": dict(response.headers),
            }

            if self._redis:
                self._redis.setex(cache_key, self._ttl, json.dumps(cache_data))
            else:
                with self._lock:
                    self._in_memory_cache[cache_key] = cache_data

            return JSONResponse(
                content=body_json,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        return response


def generate_idempotency_key() -> str:
    """Generate a new idempotency key (UUID4)."""
    return str(uuid.uuid4())


__all__ = [
    "IdempotencyMiddleware",
    "generate_idempotency_key",
    "REDIS_AVAILABLE",
]
