"""Unit tests for OutboxService - transactional outbox pattern.

Tests cover:
  - Event creation and persistence
  - Acquire pending events (destructive read)
  - Stuck event recovery
  - Mark published/failed
  - Exponential backoff
  - DLQ movement
  - DLQ replay
  - Queue statistics
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from platform_api.db.models import OutboxDlq
from platform_api.services.outbox import (
    MAX_PENDING_EVENTS_LIMIT,
    STUCK_PROCESSING_THRESHOLD_SECONDS,
    OutboxEventStatus,
    OutboxService,
)
from platform_api.tenant_context import clear_tenant_context, set_tenant_context


class TestAddEvent:
    """Tests for OutboxService.add_event()."""

    def test_add_event_persists_in_transaction(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="workflow_run",
            aggregate_id=str(uuid.uuid4()),
            event_type="workflow_run.created",
            payload={"flow_key": "test", "parameters": {}},
        )

        assert event.id is not None
        assert event.status == OutboxEventStatus.pending
        assert event.aggregate_type == "workflow_run"
        assert event.retry_count == 0
        db.flush()

    def test_add_event_sets_default_max_retries(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
        )

        assert event.max_retries == 5

    def test_add_event_serializes_payload_to_json(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        payload = {"key": "value", "nested": {"items": [1, 2, 3]}}
        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            payload=payload,
        )

        assert json.loads(event.payload_json) == payload

    def test_add_event_with_none_payload(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            payload=None,
        )

        assert event.payload_json is None

    def test_add_event_uses_current_tenant_context(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)
        workspace = seeded_db["workspace"]

        set_tenant_context(workspace.tenant_id, workspace.id)
        try:
            event = service.add_event(
                aggregate_type="workflow_run",
                aggregate_id="123",
                event_type="workflow_run.created",
            )
        finally:
            clear_tenant_context()

        assert event.tenant_id == workspace.tenant_id
        assert event.workspace_id == workspace.id


class TestAcquirePendingEvents:
    """Tests for OutboxService.acquire_pending_events()."""

    def test_acquire_pending_events_marks_processing(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
        )
        db.commit()

        acquired = service.acquire_pending_events(limit=10)

        assert len(acquired) == 1
        assert acquired[0].id == event.id
        assert acquired[0].status == OutboxEventStatus.processing

    def test_acquire_pending_events_respects_next_retry_at(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        future_event = service.add_event(
            aggregate_type="test",
            aggregate_id="future",
            event_type="test.event",
        )
        future_event.next_retry_at = datetime.now(UTC) + timedelta(hours=1)

        ready_event = service.add_event(
            aggregate_type="test",
            aggregate_id="ready",
            event_type="test.event",
        )
        db.commit()

        acquired = service.acquire_pending_events(limit=10)

        assert len(acquired) == 1
        assert acquired[0].id == ready_event.id

    def test_acquire_pending_events_validates_limit_range(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        with pytest.raises(ValueError, match="limit must be between"):
            service.acquire_pending_events(limit=0)

        with pytest.raises(ValueError, match="limit must be between"):
            service.acquire_pending_events(limit=MAX_PENDING_EVENTS_LIMIT + 1)

    def test_acquire_pending_events_skips_max_retries_exceeded(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        exhausted_event = service.add_event(
            aggregate_type="test",
            aggregate_id="exhausted",
            event_type="test.event",
            max_retries=3,
        )
        exhausted_event.retry_count = 3

        ready_event = service.add_event(
            aggregate_type="test",
            aggregate_id="ready",
            event_type="test.event",
        )
        db.commit()

        acquired = service.acquire_pending_events(limit=10)

        assert len(acquired) == 1
        assert acquired[0].id == ready_event.id

    def test_acquire_pending_events_returns_empty_when_none_pending(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)
        db.commit()

        acquired = service.acquire_pending_events(limit=10)

        assert acquired == []


class TestRecoverStuckEvents:
    """Tests for OutboxService.recover_stuck_events()."""

    def test_recover_stuck_events_resets_to_pending(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        stuck_event = service.add_event(
            aggregate_type="test",
            aggregate_id="stuck",
            event_type="test.event",
        )
        stuck_event.status = OutboxEventStatus.processing
        stuck_event.created_at = datetime.now(UTC) - timedelta(
            seconds=STUCK_PROCESSING_THRESHOLD_SECONDS + 60
        )
        db.commit()

        recovered = service.recover_stuck_events()

        assert recovered == 1
        db.refresh(stuck_event)
        assert stuck_event.status == OutboxEventStatus.pending
        assert stuck_event.retry_count == 1
        assert "Recovered from stuck" in stuck_event.last_error

    def test_recover_stuck_events_skips_recent_processing(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        recent_event = service.add_event(
            aggregate_type="test",
            aggregate_id="recent",
            event_type="test.event",
        )
        recent_event.status = OutboxEventStatus.processing
        recent_event.created_at = datetime.now(UTC) - timedelta(seconds=60)
        db.commit()

        recovered = service.recover_stuck_events()

        assert recovered == 0
        db.refresh(recent_event)
        assert recent_event.status == OutboxEventStatus.processing


class TestMarkPublished:
    """Tests for OutboxService.mark_published()."""

    def test_mark_published_sets_timestamp(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
        )
        db.flush()

        service.mark_published(event)

        assert event.status == OutboxEventStatus.published
        assert event.published_at is not None
        assert event.published_at <= datetime.now(UTC)


class TestMarkFailed:
    """Tests for OutboxService.mark_failed()."""

    def test_mark_failed_exponential_backoff(self, seeded_db: dict, monkeypatch) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        monkeypatch.setattr("platform_api.core.config.settings.webhook_backoff_base_seconds", 1)
        monkeypatch.setattr("platform_api.core.config.settings.webhook_backoff_max_seconds", 300)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            max_retries=5,
        )
        event.retry_count = 0
        db.flush()

        moved_to_dlq = service.mark_failed(event, "Test error", retry=True)

        assert moved_to_dlq is False
        assert event.status == OutboxEventStatus.pending
        assert event.retry_count == 1
        assert event.next_retry_at is not None
        expected_backoff = 1 * (2**1)
        actual_backoff = (event.next_retry_at - datetime.now(UTC)).total_seconds()
        assert abs(actual_backoff - expected_backoff) < 2

    def test_mark_failed_moves_to_dlq_after_max_retries(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            max_retries=3,
        )
        event.retry_count = 2
        db.flush()

        moved_to_dlq = service.mark_failed(event, "Final error", retry=True)

        assert moved_to_dlq is True

        dlq_entries = db.query(OutboxDlq).all()
        assert len(dlq_entries) == 1
        assert dlq_entries[0].original_event_id == event.id
        assert dlq_entries[0].final_error == "Final error"

    def test_mark_failed_truncates_long_error(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            max_retries=1,
        )
        event.retry_count = 0
        db.flush()

        long_error = "x" * 2000
        service.mark_failed(event, long_error, retry=False)

        assert len(event.last_error) == 1000

    def test_mark_failed_no_retry_sets_failed_status(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event(
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            max_retries=5,
        )
        event.retry_count = 2
        db.flush()

        moved_to_dlq = service.mark_failed(event, "Error", retry=False)

        assert moved_to_dlq is True
        assert event.status == OutboxEventStatus.failed


class TestReplayDlqEvent:
    """Tests for OutboxService.replay_dlq_event()."""

    def test_replay_dlq_event_creates_new_outbox_event(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        dlq_entry = OutboxDlq(
            original_event_id=uuid.uuid4(),
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            payload_json='{"key": "value"}',
            final_error="Previous failure",
            retry_count=5,
            original_created_at=datetime.now(UTC),
        )
        db.add(dlq_entry)
        db.commit()

        new_event = service.replay_dlq_event(dlq_entry.id)

        assert new_event.id is not None
        assert new_event.aggregate_type == "test"
        assert new_event.event_type == "test.event"
        assert json.loads(new_event.payload_json) == {"key": "value"}

        db.refresh(dlq_entry)
        assert dlq_entry.reviewed is True
        assert dlq_entry.resolution_note == "Replayed to outbox"

    def test_replay_dlq_event_raises_for_not_found(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        with pytest.raises(ValueError, match="DLQ event not found"):
            service.replay_dlq_event(uuid.uuid4())

    def test_replay_dlq_event_handles_corrupted_json(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        dlq_entry = OutboxDlq(
            original_event_id=uuid.uuid4(),
            aggregate_type="test",
            aggregate_id="123",
            event_type="test.event",
            payload_json="not valid json {{{",
            final_error="Previous failure",
            retry_count=5,
            original_created_at=datetime.now(UTC),
        )
        db.add(dlq_entry)
        db.commit()

        with pytest.raises(ValueError, match="corrupted payload"):
            service.replay_dlq_event(dlq_entry.id)

        db.refresh(dlq_entry)
        assert dlq_entry.reviewed is True
        assert "Corrupted payload JSON" in dlq_entry.resolution_note


class TestGetQueueStats:
    """Tests for OutboxService.get_queue_stats()."""

    def test_get_queue_stats_returns_correct_counts(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        service.add_event("test", "1", "test.event")
        service.add_event("test", "2", "test.event")

        processing = service.add_event("test", "3", "test.event")
        processing.status = OutboxEventStatus.processing

        failed = service.add_event("test", "4", "test.event")
        failed.status = OutboxEventStatus.failed

        dlq = OutboxDlq(
            original_event_id=uuid.uuid4(),
            aggregate_type="test",
            aggregate_id="5",
            event_type="test.event",
            retry_count=5,
            original_created_at=datetime.now(UTC),
            reviewed=False,
        )
        db.add(dlq)
        db.commit()

        stats = service.get_queue_stats()

        assert stats["pending"] == 2
        assert stats["processing"] == 1
        assert stats["failed"] == 1
        assert stats["dlq"] == 1


class TestProcessPendingEvents:
    """Tests for OutboxService.process_pending_events()."""

    @pytest.mark.asyncio
    async def test_process_pending_events_publisher_success(self, seeded_db: dict) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        event = service.add_event("test", "1", "test.event")
        db.commit()

        async def success_publisher(e):
            pass

        stats = await service.process_pending_events(publisher=success_publisher, batch_size=10)

        assert stats["published"] == 1
        assert stats["failed"] == 0
        db.refresh(event)
        assert event.status == OutboxEventStatus.published

    @pytest.mark.asyncio
    async def test_process_pending_events_publisher_failure_retries(
        self, seeded_db: dict, monkeypatch
    ) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        monkeypatch.setattr("platform_api.core.config.settings.webhook_backoff_base_seconds", 1)
        monkeypatch.setattr("platform_api.core.config.settings.webhook_backoff_max_seconds", 300)

        event = service.add_event("test", "1", "test.event", max_retries=3)
        db.commit()

        async def fail_publisher(e):
            raise RuntimeError("Publishing failed")

        stats = await service.process_pending_events(publisher=fail_publisher, batch_size=10)

        assert stats["published"] == 0
        assert stats["retried"] == 1
        db.refresh(event)
        assert event.status == OutboxEventStatus.pending
        assert event.retry_count == 1

    @pytest.mark.asyncio
    async def test_process_pending_events_moves_to_dlq_after_max_retries(
        self, seeded_db: dict
    ) -> None:
        db = seeded_db["db"]
        service = OutboxService(db)

        service.add_event("test", "1", "test.event", max_retries=1)
        db.commit()

        async def fail_publisher(e):
            raise RuntimeError("Publishing failed")

        stats = await service.process_pending_events(publisher=fail_publisher, batch_size=10)

        assert stats["dlq"] == 1

        dlq_entries = db.query(OutboxDlq).all()
        assert len(dlq_entries) == 1
