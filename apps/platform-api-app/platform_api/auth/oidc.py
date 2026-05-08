from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from platform_api.core.config import settings
from platform_api.core.egress_policy import enforce_egress_policy

logger = logging.getLogger(__name__)

OIDC_TIMEOUT_SECONDS = 10
OIDC_MAX_RETRIES = 3
OIDC_RETRY_BASE_DELAY = 0.5
OIDC_CIRCUIT_BREAKER_THRESHOLD = 3
OIDC_CIRCUIT_BREAKER_RESET_SECONDS = 60
OIDC_JWKS_CACHE_SECONDS = 600  # 10 minutes (reduced from 1 hour for key rotation)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for OIDC endpoint."""
    failure_count: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    audience: str
    jwks_url: str


class OIDCVerifier:
    def __init__(self, config: OIDCConfig) -> None:
        self._config = config
        self._jwks: dict | None = None
        self._jwks_fetched_at: float | None = None
        self._circuit_breaker: CircuitBreakerState = field(default_factory=CircuitBreakerState)
        self._circuit_breaker = CircuitBreakerState()

    def _jwks_is_stale(self) -> bool:
        if self._jwks is None or self._jwks_fetched_at is None:
            return True
        return (time.time() - self._jwks_fetched_at) > OIDC_JWKS_CACHE_SECONDS

    def invalidate_jwks_cache(self) -> None:
        """Manually invalidate the JWKS cache.

        Call this method when you know the identity provider has rotated
        signing keys, or when authentication fails due to invalid keys.
        """
        self._jwks = None
        self._jwks_fetched_at = None
        logger.info("JWKS cache manually invalidated")

    def _is_circuit_open(self) -> bool:
        """Check if circuit breaker is open."""
        if not self._circuit_breaker.is_open:
            return False
        if time.time() - self._circuit_breaker.last_failure_time > OIDC_CIRCUIT_BREAKER_RESET_SECONDS:
            logger.info("OIDC circuit breaker reset, attempting recovery")
            self._circuit_breaker.is_open = False
            self._circuit_breaker.failure_count = 0
            return False
        return True

    def _record_success(self) -> None:
        """Record successful OIDC call."""
        self._circuit_breaker.failure_count = 0
        self._circuit_breaker.is_open = False

    def _record_failure(self) -> None:
        """Record failed OIDC call."""
        self._circuit_breaker.failure_count += 1
        self._circuit_breaker.last_failure_time = time.time()
        if self._circuit_breaker.failure_count >= OIDC_CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_breaker.is_open = True
            logger.error(
                "OIDC circuit breaker OPEN after %d failures. "
                "Will retry after %d seconds.",
                self._circuit_breaker.failure_count,
                OIDC_CIRCUIT_BREAKER_RESET_SECONDS,
            )

    async def _get_jwks(self) -> dict:
        if not self._jwks_is_stale():
            assert self._jwks is not None
            return self._jwks

        enforce_egress_policy(
            url=self._config.jwks_url,
            allowed_hosts=settings.egress_allowed_hosts,
            strict_mode=settings.egress_strict_mode,
            purpose="oidc_jwks_fetch",
        )

        if self._is_circuit_open():
            raise ValueError(
                "OIDC service unavailable (circuit breaker open). "
                "Authentication temporarily disabled."
            )

        last_error: Exception | None = None
        for attempt in range(OIDC_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=OIDC_TIMEOUT_SECONDS) as client:
                    resp = await client.get(self._config.jwks_url)
                    resp.raise_for_status()
                    jwks = resp.json()
                    self._jwks = jwks
                    self._jwks_fetched_at = time.time()
                    self._record_success()
                    return jwks
            except Exception as e:
                last_error = e
                logger.warning(
                    "OIDC JWKS fetch attempt %d/%d failed: %s",
                    attempt + 1, OIDC_MAX_RETRIES, e,
                )
                if attempt < OIDC_MAX_RETRIES - 1:
                    delay = OIDC_RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        self._record_failure()
        raise ValueError(
            f"Failed to fetch OIDC JWKS after {OIDC_MAX_RETRIES} attempts. "
            "Authentication service unavailable."
        ) from last_error

    async def verify(self, token: str) -> dict:
        jwks = await self._get_jwks()
        try:
            return jwt.decode(
                token,
                jwks,
                algorithms=["RS256"],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"verify_aud": bool(self._config.audience)},
            )
        except JWTError:
            raise ValueError("Invalid token") from None

__all__ = ["OIDCConfig", "OIDCVerifier"]
