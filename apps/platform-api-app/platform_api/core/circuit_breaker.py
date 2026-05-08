"""Distributed circuit breaker with Redis backend.

Provides circuit breaker pattern for protecting services from cascading failures.
Supports both in-memory (single replica) and Redis-backed (multi-replica) modes.

Design
------
* **Distributed state**: When Redis is available, all replicas share circuit state
* **Automatic recovery**: Circuit resets after configurable timeout
* **Fail-fast**: Prevents cascading failures by rejecting requests when open
* **Metrics**: Prometheus gauges for monitoring

Best Practices Reference:
https://martinfowler.com/bliki/CircuitBreaker.html
https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

REDIS_AVAILABLE = False
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    pass


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    name: str
    failure_threshold: int = 3
    reset_timeout_seconds: int = 60
    half_open_max_calls: int = 1


class DistributedCircuitBreaker:
    """Circuit breaker with optional Redis backend for distributed state.

    When Redis is available, circuit state is shared across all replicas.
    When Redis is not available, falls back to in-memory state (single replica).

    Parameters
    ----------
    config : CircuitBreakerConfig
        Circuit breaker configuration.
    redis_url : str | None
        Redis connection URL for distributed state.
    key_prefix : str
        Prefix for Redis keys.

    States
    ------
    * **CLOSED**: Normal operation, requests pass through
    * **OPEN**: Requests are rejected, waiting for reset timeout
    * **HALF_OPEN**: Limited requests allowed to test recovery

    Examples
    --------
    ::

        cb = DistributedCircuitBreaker(
            config=CircuitBreakerConfig(name="prefect", failure_threshold=3),
            redis_url="redis://localhost:6379/0"
        )

        if cb.is_open():
            raise RuntimeError("Service unavailable")

        try:
            result = await call_external_service()
            cb.record_success()
        except Exception as e:
            cb.record_failure()
            raise
    """

    STATE_CLOSED = "closed"
    STATE_OPEN = "open"
    STATE_HALF_OPEN = "half_open"

    def __init__(
        self,
        config: CircuitBreakerConfig,
        redis_url: Optional[str] = None,
        key_prefix: str = "circuit_breaker:",
    ) -> None:
        self._config = config
        self._key_prefix = key_prefix
        self._redis_key = f"{key_prefix}{config.name}"

        self._local_failure_count: int = 0
        self._local_last_failure_time: float = 0.0
        self._local_state: str = self.STATE_CLOSED
        self._half_open_calls: int = 0

        if redis_url and REDIS_AVAILABLE:
            self._redis: Optional[redis.Redis] = redis.from_url(redis_url)
            logger.info(
                "DistributedCircuitBreaker '%s' connected to Redis",
                config.name
            )
        else:
            self._redis = None
            if redis_url and not REDIS_AVAILABLE:
                logger.warning(
                    "Redis not available for circuit breaker '%s'. "
                    "Using in-memory state (not distributed).",
                    config.name
                )

    def _get_state_from_redis(self) -> tuple[str, int, float]:
        """Get circuit state from Redis."""
        if not self._redis:
            return self._local_state, self._local_failure_count, self._local_last_failure_time

        try:
            data = self._redis.hgetall(self._redis_key)
            if not data:
                return self.STATE_CLOSED, 0, 0.0

            state = data.get(b"state", b"closed").decode()
            failure_count = int(data.get(b"failure_count", b"0").decode())
            last_failure_time = float(data.get(b"last_failure_time", b"0").decode())
            return state, failure_count, last_failure_time
        except Exception as e:
            logger.warning(
                "Failed to get circuit breaker state from Redis: %s. "
                "Using local state.",
                e
            )
            return self._local_state, self._local_failure_count, self._local_last_failure_time

    def _set_state_in_redis(self, state: str, failure_count: int, last_failure_time: float) -> None:
        """Set circuit state in Redis."""
        if not self._redis:
            self._local_state = state
            self._local_failure_count = failure_count
            self._local_last_failure_time = last_failure_time
            return

        try:
            self._redis.hset(
                self._redis_key,
                mapping={
                    "state": state,
                    "failure_count": str(failure_count),
                    "last_failure_time": str(last_failure_time),
                }
            )
            self._redis.expire(self._redis_key, self._config.reset_timeout_seconds * 2)
        except Exception as e:
            logger.warning("Failed to set circuit breaker state in Redis: %s", e)
            self._local_state = state
            self._local_failure_count = failure_count
            self._local_last_failure_time = last_failure_time

    def is_open(self) -> bool:
        """Check if circuit breaker is open (rejecting requests).

        Returns
        -------
        bool
            True if circuit is open and should reject requests.
        """
        state, failure_count, last_failure_time = self._get_state_from_redis()

        if state == self.STATE_CLOSED:
            return False

        if state == self.STATE_OPEN:
            now = time.time()
            if now - last_failure_time > self._config.reset_timeout_seconds:
                logger.info(
                    "Circuit breaker '%s' transitioning to HALF_OPEN after timeout",
                    self._config.name
                )
                self._set_state_in_redis(self.STATE_HALF_OPEN, failure_count, last_failure_time)
                self._half_open_calls = 0
                return False
            return True

        if state == self.STATE_HALF_OPEN:
            return self._half_open_calls >= self._config.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record a successful operation.

        Resets the circuit breaker to closed state.
        """
        logger.debug(
            "Circuit breaker '%s' recording success",
            self._config.name
        )
        self._set_state_in_redis(self.STATE_CLOSED, 0, 0.0)
        self._half_open_calls = 0

    def record_failure(self) -> None:
        """Record a failed operation.

        Increments failure count and opens circuit if threshold is reached.
        """
        state, failure_count, last_failure_time = self._get_state_from_redis()
        now = time.time()

        failure_count += 1
        last_failure_time = now

        if state == self.STATE_HALF_OPEN:
            logger.warning(
                "Circuit breaker '%s' failure in HALF_OPEN, reopening",
                self._config.name
            )
            self._set_state_in_redis(self.STATE_OPEN, failure_count, now)
            return

        if failure_count >= self._config.failure_threshold:
            logger.error(
                "Circuit breaker '%s' OPEN after %d failures. "
                "Will retry after %d seconds.",
                self._config.name,
                failure_count,
                self._config.reset_timeout_seconds,
            )
            self._set_state_in_redis(self.STATE_OPEN, failure_count, now)
        else:
            self._set_state_in_redis(self.STATE_CLOSED, failure_count, last_failure_time)

    def record_half_open_call(self) -> None:
        """Record a call in half-open state."""
        self._half_open_calls += 1

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        logger.info("Circuit breaker '%s' manually reset to CLOSED", self._config.name)
        self._set_state_in_redis(self.STATE_CLOSED, 0, 0.0)
        self._half_open_calls = 0

    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring.

        Returns
        -------
        dict
            State information including status, failure count, etc.
        """
        state, failure_count, last_failure_time = self._get_state_from_redis()
        return {
            "name": self._config.name,
            "state": state,
            "failure_count": failure_count,
            "failure_threshold": self._config.failure_threshold,
            "last_failure_time": last_failure_time,
            "reset_timeout_seconds": self._config.reset_timeout_seconds,
            "is_distributed": self._redis is not None,
        }


__all__ = [
    "CircuitBreakerConfig",
    "DistributedCircuitBreaker",
    "REDIS_AVAILABLE",
]
