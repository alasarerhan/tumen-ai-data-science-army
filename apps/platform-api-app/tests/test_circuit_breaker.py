"""Unit tests for DistributedCircuitBreaker.

Tests cover:
  - State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
  - Failure threshold handling
  - Timeout-based recovery
  - Half-open limited calls
  - Redis fallback to in-memory
  - Manual reset
  - State monitoring
"""

from __future__ import annotations

import threading
import time

from platform_api.core.circuit_breaker import (
    CircuitBreakerConfig,
    DistributedCircuitBreaker,
)


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state machine."""

    def test_initial_state_is_closed(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        cb = DistributedCircuitBreaker(config)

        assert cb.is_open() is False
        state = cb.get_state()
        assert state["state"] == DistributedCircuitBreaker.STATE_CLOSED

    def test_circuit_opens_after_threshold_failures(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=3)
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        assert cb.is_open() is False

        cb.record_failure()
        assert cb.is_open() is False

        cb.record_failure()
        assert cb.is_open() is True

        state = cb.get_state()
        assert state["state"] == DistributedCircuitBreaker.STATE_OPEN

    def test_circuit_open_is_open_returns_true(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()

        assert cb.is_open() is True

    def test_circuit_transitions_to_half_open_after_timeout(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            reset_timeout_seconds=0.1,
        )
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        assert cb.is_open() is True

        time.sleep(0.15)

        assert cb.is_open() is False
        state = cb.get_state()
        assert state["state"] == DistributedCircuitBreaker.STATE_HALF_OPEN

    def test_half_open_allows_limited_calls(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            reset_timeout_seconds=0.1,
            half_open_max_calls=2,
        )
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        time.sleep(0.15)

        assert cb.is_open() is False

        cb.record_half_open_call()
        assert cb.is_open() is False

        cb.record_half_open_call()
        assert cb.is_open() is True

    def test_record_success_resets_to_closed(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            reset_timeout_seconds=0.1,
        )
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        time.sleep(0.15)
        cb.is_open()

        cb.record_success()

        assert cb.is_open() is False
        state = cb.get_state()
        assert state["state"] == DistributedCircuitBreaker.STATE_CLOSED

    def test_record_failure_in_half_open_reopens(self):
        config = CircuitBreakerConfig(
            name="test",
            failure_threshold=1,
            reset_timeout_seconds=0.1,
        )
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        time.sleep(0.15)
        cb.is_open()

        cb.record_failure()

        state = cb.get_state()
        assert state["state"] == DistributedCircuitBreaker.STATE_OPEN


class TestCircuitBreakerRedisFallback:
    """Tests for Redis fallback behavior."""

    def test_redis_unavailable_uses_local_state(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=2)
        cb = DistributedCircuitBreaker(config, redis_url=None)

        assert cb._redis is None

        cb.record_failure()
        cb.record_failure()

        assert cb.is_open() is True

    def test_redis_connection_failure_falls_back_gracefully(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=2)
        cb = DistributedCircuitBreaker(config, redis_url="redis://invalid-host:6379")

        cb.record_failure()
        cb.record_failure()

        assert cb.is_open() is True


class TestCircuitBreakerMonitoring:
    """Tests for circuit breaker monitoring."""

    def test_get_state_returns_current_status(self):
        config = CircuitBreakerConfig(
            name="test-service",
            failure_threshold=5,
            reset_timeout_seconds=60,
        )
        cb = DistributedCircuitBreaker(config)

        state = cb.get_state()

        assert state["name"] == "test-service"
        assert state["state"] == DistributedCircuitBreaker.STATE_CLOSED
        assert state["failure_count"] == 0
        assert state["failure_threshold"] == 5
        assert state["reset_timeout_seconds"] == 60
        assert state["is_distributed"] is False

    def test_get_state_shows_failure_count(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=5)
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        cb.record_failure()

        state = cb.get_state()
        assert state["failure_count"] == 2


class TestCircuitBreakerManualReset:
    """Tests for manual reset functionality."""

    def test_manual_reset(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=1)
        cb = DistributedCircuitBreaker(config)

        cb.record_failure()
        assert cb.is_open() is True

        cb.reset()

        assert cb.is_open() is False
        state = cb.get_state()
        assert state["state"] == DistributedCircuitBreaker.STATE_CLOSED
        assert state["failure_count"] == 0


class TestCircuitBreakerThreadSafety:
    """Tests for thread safety."""

    def test_concurrent_failure_recording(self):
        config = CircuitBreakerConfig(name="test", failure_threshold=100)
        cb = DistributedCircuitBreaker(config)

        def record_failures(count: int):
            for _ in range(count):
                cb.record_failure()

        threads = [threading.Thread(target=record_failures, args=(25,)) for _ in range(4)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = cb.get_state()
        assert state["failure_count"] == 100
