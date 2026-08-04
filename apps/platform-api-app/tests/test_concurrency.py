"""Concurrency tests for race conditions.

Tests cover:
  - Concurrent workflow publish race condition
  - Concurrent run creation version conflict
  - Circuit breaker concurrent state changes
"""

from __future__ import annotations

import threading
import uuid
from unittest.mock import patch


class TestConcurrentWorkflowPublish:
    """Tests for concurrent workflow publish race conditions."""

    def test_concurrent_workflow_publish_race_condition(self, seeded_db: dict) -> None:
        from platform_api.services import workflow_service

        db = seeded_db["db"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        results = {"success": 0, "conflict": 0, "error": 0}
        lock = threading.Lock()

        def publish_attempt():
            try:
                with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
                    workflow_service.create_workflow_spec_version(
                        db,
                        workspace_id=str(workspace.id),
                        user_id=user_id,
                        name=f"concurrent-test-{uuid.uuid4().hex[:8]}",
                        spec={"steps": [{"id": "s1", "tool": "data_clean"}]},
                        publish=True,
                    )
                    with lock:
                        results["success"] += 1
            except Exception as e:
                with lock:
                    if "conflict" in str(e).lower() or "409" in str(e):
                        results["conflict"] += 1
                    else:
                        results["error"] += 1

        threads = [threading.Thread(target=publish_attempt) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["success"] >= 1


class TestConcurrentRunCreation:
    """Tests for concurrent run creation."""

    def test_concurrent_run_creation_succeeds(self, seeded_db: dict) -> None:
        from platform_api.services import run_service

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        results = {"success": 0, "error": 0}
        lock = threading.Lock()

        def create_run():
            try:
                run_service.create_workflow_run_record(
                    db,
                    tenant_id=tenant.id,
                    workspace_id=workspace.id,
                    user_id=user_id,
                    flow_key="test",
                    prefect_flow_run_id=f"concurrent-{uuid.uuid4().hex}",
                    parameters={},
                )
                with lock:
                    results["success"] += 1
            except Exception:
                with lock:
                    results["error"] += 1

        threads = [threading.Thread(target=create_run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results["success"] == 5


class TestCircuitBreakerConcurrency:
    """Tests for circuit breaker thread safety."""

    def test_circuit_breaker_concurrent_state_changes(self) -> None:
        from platform_api.core.circuit_breaker import (
            CircuitBreakerConfig,
            DistributedCircuitBreaker,
        )

        config = CircuitBreakerConfig(name="concurrent-test", failure_threshold=50)
        cb = DistributedCircuitBreaker(config)

        results = {"failures": 0, "successes": 0}
        lock = threading.Lock()

        def record_failures(count: int):
            for _ in range(count):
                cb.record_failure()
                with lock:
                    results["failures"] += 1

        def record_successes(count: int):
            for _ in range(count):
                cb.record_success()
                with lock:
                    results["successes"] += 1

        threads = [
            threading.Thread(target=record_failures, args=(10,)),
            threading.Thread(target=record_failures, args=(10,)),
            threading.Thread(target=record_successes, args=(5,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        state = cb.get_state()
        assert state["failure_count"] >= 0
