"""Outbox pattern implementation for reliable event publishing.

Ensures atomic database writes + event publishing by storing events
in an outbox table within the same transaction. A background worker
then publishes events to external systems (Prefect, message queues).

Design
------
* **Atomicity**: Database write + outbox insert in same transaction
* **At-least-once delivery**: Events are retried until confirmed
* **Idempotency**: Each event has unique ID for deduplication
* **Ordering**: Events processed in creation order per aggregate
* **DLQ**: Failed events moved to dead letter queue for inspection
* **Metrics**: Prometheus gauges for queue depth monitoring

Best Practices Reference:
https://microservices.io/patterns/data/transactional-outbox.html
https://levelup.gitconnected.com/transactional-outbox-with-rabbitmq-part-2-handling-retries-dead-letter-queues-and-observability-d53217cf45e9

Usage
-----
::

    from platform_api.services.outbox import OutboxService

    # In your service, within a transaction:
    async def create_workflow_run(db: Session, ...):
        run = WorkflowRun(...)
        db.add(run)

        outbox = OutboxService(db)
        outbox.add_event(
            aggregate_type="workflow_run",
            aggregate_id=str(run.id),
            event_type="workflow_run.created",
            payload={"flow_key": flow_key, "parameters": params}
        )

        db.commit()  # Both run and event saved atomically

    # Background worker publishes events:
    async def outbox_worker():
        outbox = OutboxService(db)
        await outbox.process_pending_events(publisher=prefect_publisher)
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Gauge
from sqlalchemy import DateTime, Index, String, Text, func, select, update
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from platform_api.db.base import Base
from platform_api.tenant_context import get_current_tenant_id, get_current_workspace_id

logger = logging.getLogger(__name__)


MAX_PENDING_EVENTS_LIMIT = 100
MIN_PENDING_EVENTS_LIMIT = 1
DEFAULT_BATCH_SIZE = 10
STUCK_PROCESSING_THRESHOLD_SECONDS = 300


OUTBOX_STUCK_GAUGE = Gauge(
    "platform_api_outbox_stuck_total",
    "Number of events stuck in processing state",
    registry=None,
)


OUTBOX_PENDING_GAUGE = Gauge(
    "platform_api_outbox_pending_total",
    "Number of pending outbox events waiting to be published",
    registry=None,
)

OUTBOX_PROCESSING_GAUGE = Gauge(
    "platform_api_outbox_processing_total",
    "Number of outbox events currently being processed",
    registry=None,
)

OUTBOX_FAILED_GAUGE = Gauge(
    "platform_api_outbox_failed_total",
    "Number of failed outbox events (exceeded max retries)",
    registry=None,
)

OUTBOX_DLQ_GAUGE = Gauge(
    "platform_api_outbox_dlq_total",
    "Number of events in dead letter queue",
    registry=None,
)


class OutboxEventStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    published = "published"
    failed = "failed"


class OutboxEvent(Base):
    """Outbox event for reliable event publishing.

    Events are stored in the database within the same transaction
    as the aggregate change, ensuring atomicity.
    """

    __tablename__ = "outbox_events"
    __table_args__ = (
        Index("ix_outbox_events_status_created", "status", "created_at"),
        Index("ix_outbox_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_outbox_events_status_retry_created", "status", "next_retry_at", "created_at"),
        Index("ix_outbox_events_tenant_status_created", "tenant_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OutboxEventStatus] = mapped_column(
        String(30), nullable=False, default=OutboxEventStatus.pending
    )
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=5, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutboxService:
    """Service for managing outbox events.

    Provides methods to add events within a transaction and
    process pending events in a background worker.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def add_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        max_retries: int = 5,
        tenant_id: uuid.UUID | str | None = None,
        workspace_id: uuid.UUID | str | None = None,
    ) -> OutboxEvent:
        """Add an event to the outbox within the current transaction.

        This should be called before db.commit() in the same transaction
        as the aggregate change.

        Parameters
        ----------
        aggregate_type : str
            Type of aggregate (e.g., "workflow_run", "chat_session").
        aggregate_id : str
            ID of the aggregate.
        event_type : str
            Event type (e.g., "workflow_run.created", "workflow_run.completed").
        payload : dict | None
            Event payload (will be JSON-serialized).
        max_retries : int
            Maximum retry attempts for publishing.

        Returns
        -------
        OutboxEvent
            The created outbox event.
        """
        resolved_tenant_id = tenant_id or get_current_tenant_id()
        resolved_workspace_id = workspace_id or get_current_workspace_id()
        if isinstance(resolved_tenant_id, str):
            resolved_tenant_id = uuid.UUID(resolved_tenant_id)
        if isinstance(resolved_workspace_id, str):
            resolved_workspace_id = uuid.UUID(resolved_workspace_id)

        event = OutboxEvent(
            tenant_id=resolved_tenant_id,
            workspace_id=resolved_workspace_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=json.dumps(payload) if payload else None,
            max_retries=max_retries,
        )
        self._db.add(event)
        self._db.flush()
        logger.debug(
            "Added outbox event: id=%s, type=%s, aggregate=%s/%s",
            event.id,
            event_type,
            aggregate_type,
            aggregate_id,
        )
        return event

    def recover_stuck_events(self) -> int:
        """Recover events stuck in 'processing' state.

        Events that have been in 'processing' state for longer than
        STUCK_PROCESSING_THRESHOLD_SECONDS are reset to 'pending'.

        Returns
        -------
        int
            Number of events recovered.
        """
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=STUCK_PROCESSING_THRESHOLD_SECONDS)

        stuck_events = list(
            self._db.execute(
                select(OutboxEvent).where(
                    OutboxEvent.status == OutboxEventStatus.processing,
                    OutboxEvent.created_at < threshold,
                )
            ).scalars()
        )

        recovered = 0
        for event in stuck_events:
            event.status = OutboxEventStatus.pending
            event.retry_count += 1
            event.last_error = f"Recovered from stuck 'processing' state after {STUCK_PROCESSING_THRESHOLD_SECONDS}s"
            self._db.add(event)
            recovered += 1
            logger.warning(
                "Recovered stuck event: id=%s, type=%s, was processing since %s",
                event.id,
                event.event_type,
                event.created_at,
            )

        if recovered > 0:
            self._db.commit()
            OUTBOX_STUCK_GAUGE.set(recovered)

        return recovered

    def acquire_pending_events(
        self,
        limit: int = DEFAULT_BATCH_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> list[OutboxEvent]:
        """Acquire pending events for processing (DESTRUCTIVE READ).

        WARNING: This method MUTATES database state and COMMITS the transaction.
        Events are marked as 'processing' to prevent duplicate processing.
        Respects next_retry_at for exponential backoff.

        This is a destructive read operation - acquired events cannot be
        re-acquired until they are recovered from stuck state.

        Parameters
        ----------
        limit : int
            Maximum number of events to return. Must be between 1 and 100.
        batch_size : int
            Number of events to process in one batch. Must be between 1 and 100.

        Returns
        -------
        list[OutboxEvent]
            List of pending events marked as 'processing'.

        Raises
        ------
        ValueError
            If limit or batch_size is outside valid range.
        """
        if limit < MIN_PENDING_EVENTS_LIMIT or limit > MAX_PENDING_EVENTS_LIMIT:
            raise ValueError(
                f"limit must be between {MIN_PENDING_EVENTS_LIMIT} and {MAX_PENDING_EVENTS_LIMIT}, "
                f"got {limit}"
            )
        if batch_size < MIN_PENDING_EVENTS_LIMIT or batch_size > MAX_PENDING_EVENTS_LIMIT:
            raise ValueError(
                f"batch_size must be between {MIN_PENDING_EVENTS_LIMIT} and {MAX_PENDING_EVENTS_LIMIT}, "
                f"got {batch_size}"
            )
        now = datetime.now(UTC)
        events = list(
            self._db.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == OutboxEventStatus.pending,
                    OutboxEvent.retry_count < OutboxEvent.max_retries,
                    (OutboxEvent.next_retry_at.is_(None)) | (OutboxEvent.next_retry_at <= now),
                )
                .order_by(OutboxEvent.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).scalars()
        )

        if events:
            event_ids = [e.id for e in events]
            self._db.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id.in_(event_ids))
                .values(status=OutboxEventStatus.processing)
            )
            self._db.commit()

        return events

    def get_pending_events(
        self,
        limit: int = DEFAULT_BATCH_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> list[OutboxEvent]:
        """DEPRECATED: Use acquire_pending_events() instead.

        This method is deprecated because it mutates database state despite
        being named 'get'. Use acquire_pending_events() for clarity.
        """
        import warnings

        warnings.warn(
            "get_pending_events() is deprecated. Use acquire_pending_events() "
            "to make the destructive read behavior explicit.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.acquire_pending_events(limit=limit, batch_size=batch_size)

    def mark_published(self, event: OutboxEvent) -> None:
        """Mark an event as successfully published."""
        event.status = OutboxEventStatus.published
        event.published_at = datetime.now(UTC)
        self._db.add(event)
        self._db.flush()
        logger.debug("Event published: id=%s, type=%s", event.id, event.event_type)

    def mark_failed(
        self,
        event: OutboxEvent,
        error: str,
        retry: bool = True,
    ) -> bool:
        """Mark an event as failed.

        Parameters
        ----------
        event : OutboxEvent
            The failed event.
        error : str
            Error message.
        retry : bool
            Whether to allow retry (if under max_retries).

        Returns
        -------
        bool
            True if event was moved to DLQ, False otherwise.
        """
        from platform_api.core.config import settings

        event.last_error = error[:1000] if len(error) > 1000 else error
        event.retry_count += 1

        if retry and event.retry_count < event.max_retries:
            event.status = OutboxEventStatus.pending
            backoff = min(
                settings.webhook_backoff_base_seconds * (2**event.retry_count),
                settings.webhook_backoff_max_seconds,
            )
            event.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff)
            logger.warning(
                "Event failed (will retry in %.1fs): id=%s, attempt=%d/%d, error=%s",
                backoff,
                event.id,
                event.retry_count,
                event.max_retries,
                error[:200],
            )
            self._db.add(event)
            self._db.flush()
            return False
        else:
            event.status = OutboxEventStatus.failed
            event.next_retry_at = None
            self._db.add(event)
            moved_to_dlq = self._move_to_dlq(event, error)
            if moved_to_dlq:
                logger.error(
                    "Event moved to DLQ: id=%s, attempts=%d, error=%s",
                    event.id,
                    event.retry_count,
                    error[:200],
                )
            else:
                logger.error(
                    "Event failed (no more retries): id=%s, attempts=%d, error=%s",
                    event.id,
                    event.retry_count,
                    error[:200],
                )
            self._db.flush()
            return moved_to_dlq

    def _move_to_dlq(self, event: OutboxEvent, error: str) -> bool:
        """Move a failed event to the dead letter queue.

        Parameters
        ----------
        event : OutboxEvent
            The failed event to move.
        error : str
            The final error message.

        Returns
        -------
        bool
            True if successfully moved to DLQ.
        """
        try:
            from platform_api.db.models import OutboxDlq

            dlq_entry = OutboxDlq(
                tenant_id=event.tenant_id,
                workspace_id=event.workspace_id,
                original_event_id=event.id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                event_type=event.event_type,
                payload_json=event.payload_json,
                final_error=error[:2000] if len(error) > 2000 else error,
                retry_count=event.retry_count,
                original_created_at=event.created_at,
            )
            self._db.add(dlq_entry)
            logger.warning(
                "Event moved to DLQ: original_id=%s, event_type=%s",
                event.id,
                event.event_type,
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to move event to DLQ: event_id=%s, error=%s",
                event.id,
                str(e),
            )
            return False

    def get_dlq_events(
        self,
        limit: int = 100,
        unreviewed_only: bool = True,
        tenant_id: uuid.UUID | str | None = None,
    ) -> list:
        """Get events from the dead letter queue.

        Parameters
        ----------
        limit : int
            Maximum number of events to return.
        unreviewed_only : bool
            If True, only return events that haven't been reviewed.

        Returns
        -------
        list
            List of DLQ events.
        """
        from platform_api.db.models import OutboxDlq

        query = select(OutboxDlq)
        if tenant_id is not None:
            if isinstance(tenant_id, str):
                tenant_id = uuid.UUID(tenant_id)
            query = query.where(OutboxDlq.tenant_id == tenant_id)
        if unreviewed_only:
            query = query.where(OutboxDlq.reviewed.is_(False))
        query = query.order_by(OutboxDlq.moved_to_dlq_at.desc()).limit(limit)

        return list(self._db.execute(query).scalars())

    def replay_dlq_event(
        self,
        dlq_event_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID | str | None = None,
        reviewed_by_user_id: uuid.UUID | None = None,
    ) -> OutboxEvent:
        """Replay a DLQ event by creating a new outbox event.

        Parameters
        ----------
        dlq_event_id : uuid.UUID
            ID of the DLQ event to replay.

        Returns
        -------
        OutboxEvent
            The new outbox event created for replay.
        """
        from platform_api.db.models import OutboxDlq

        query = select(OutboxDlq).where(OutboxDlq.id == dlq_event_id)
        if tenant_id is not None:
            if isinstance(tenant_id, str):
                tenant_id = uuid.UUID(tenant_id)
            query = query.where(OutboxDlq.tenant_id == tenant_id)

        dlq_event = self._db.execute(query).scalar_one_or_none()

        if not dlq_event:
            raise ValueError(f"DLQ event not found: {dlq_event_id}")

        payload = None
        if dlq_event.payload_json:
            try:
                payload = json.loads(dlq_event.payload_json)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse payload JSON for DLQ event %s, marking as corrupted: %s",
                    dlq_event_id,
                    e,
                )
                dlq_event.reviewed = True
                dlq_event.reviewed_at = datetime.now(UTC)
                dlq_event.resolution_note = f"Corrupted payload JSON: {e}"
                self._db.add(dlq_event)
                self._db.flush()
                raise ValueError(f"DLQ event has corrupted payload: {dlq_event_id}") from e

        new_event = self.add_event(
            aggregate_type=dlq_event.aggregate_type,
            aggregate_id=dlq_event.aggregate_id,
            event_type=dlq_event.event_type,
            payload=payload,
            max_retries=5,
            tenant_id=dlq_event.tenant_id,
            workspace_id=dlq_event.workspace_id,
        )

        dlq_event.reviewed = True
        dlq_event.reviewed_at = datetime.now(UTC)
        dlq_event.reviewed_by_user_id = reviewed_by_user_id
        dlq_event.resolution_note = "Replayed to outbox"
        self._db.add(dlq_event)
        self._db.flush()

        logger.info(
            "Replayed DLQ event: dlq_id=%s, new_event_id=%s",
            dlq_event_id,
            new_event.id,
        )
        return new_event

    def get_queue_stats(self, tenant_id: uuid.UUID | str | None = None) -> dict[str, int]:
        """Get queue statistics for monitoring.

        Returns
        -------
        dict
            Dictionary with pending, processing, failed, and dlq counts.
        """
        from platform_api.db.models import OutboxDlq

        if isinstance(tenant_id, str):
            tenant_id = uuid.UUID(tenant_id)

        pending_query = select(func.count()).where(OutboxEvent.status == OutboxEventStatus.pending)
        processing_query = select(func.count()).where(
            OutboxEvent.status == OutboxEventStatus.processing
        )
        failed_query = select(func.count()).where(OutboxEvent.status == OutboxEventStatus.failed)
        dlq_query = select(func.count()).where(OutboxDlq.reviewed.is_(False))

        if tenant_id is not None:
            pending_query = pending_query.where(OutboxEvent.tenant_id == tenant_id)
            processing_query = processing_query.where(OutboxEvent.tenant_id == tenant_id)
            failed_query = failed_query.where(OutboxEvent.tenant_id == tenant_id)
            dlq_query = dlq_query.where(OutboxDlq.tenant_id == tenant_id)

        pending = self._db.execute(pending_query).scalar() or 0

        processing = self._db.execute(processing_query).scalar() or 0

        failed = self._db.execute(failed_query).scalar() or 0

        dlq_count = self._db.execute(dlq_query).scalar() or 0

        return {
            "pending": pending,
            "processing": processing,
            "failed": failed,
            "dlq": dlq_count,
        }

    def update_metrics(self) -> None:
        """Update Prometheus gauges with current queue stats."""
        stats = self.get_queue_stats()
        OUTBOX_PENDING_GAUGE.set(stats["pending"])
        OUTBOX_PROCESSING_GAUGE.set(stats["processing"])
        OUTBOX_FAILED_GAUGE.set(stats["failed"])
        OUTBOX_DLQ_GAUGE.set(stats["dlq"])

    async def process_pending_events(
        self,
        publisher: Callable[[OutboxEvent], Any],
        batch_size: int = 10,
    ) -> dict[str, int]:
        """Process pending events with the given publisher.

        Parameters
        ----------
        publisher : callable
            Async function to publish an event. Should raise on failure.
        batch_size : int
            Number of events to process in one batch.

        Returns
        -------
        dict
            Summary with 'published', 'failed', 'retried', 'dlq', 'recovered' counts.
        """
        stats = {"published": 0, "failed": 0, "retried": 0, "dlq": 0, "recovered": 0}

        stats["recovered"] = self.recover_stuck_events()

        events = self.get_pending_events(limit=batch_size)

        for event in events:
            try:
                await publisher(event)
                self.mark_published(event)
                stats["published"] += 1
            except Exception:
                error_msg = "Publishing failed"
                will_retry = event.retry_count + 1 < event.max_retries
                moved_to_dlq = self.mark_failed(event, error_msg, retry=will_retry)
                if moved_to_dlq:
                    stats["dlq"] += 1
                elif will_retry:
                    stats["retried"] += 1
                else:
                    stats["failed"] += 1

        self._db.commit()
        self.update_metrics()
        return stats


async def prefect_event_publisher(event: OutboxEvent) -> None:
    """Publisher for Prefect workflow events.

    Creates Prefect flow runs based on outbox events.

    Parameters
    ----------
    event : OutboxEvent
        The event to publish.

    Raises
    ------
    Exception
        If publishing fails.
    """
    from platform_api.services.run_orchestration_service import create_orchestration_run_id

    if event.event_type == "workflow_run.created":
        payload = json.loads(event.payload_json) if event.payload_json else {}
        flow_key = payload.get("flow_key", "unknown")
        parameters = payload.get("parameters", {})

        flow_run_id = await create_orchestration_run_id(
            flow_key=flow_key,
            parameters=parameters,
        )
        logger.info(
            "Created Prefect flow run: flow_run_id=%s, event_id=%s",
            flow_run_id,
            event.id,
        )
    else:
        logger.debug("Ignoring event type: %s", event.event_type)


__all__ = [
    "OUTBOX_DLQ_GAUGE",
    "OUTBOX_FAILED_GAUGE",
    "OUTBOX_PENDING_GAUGE",
    "OUTBOX_PROCESSING_GAUGE",
    "OUTBOX_STUCK_GAUGE",
    "OutboxEvent",
    "OutboxEventStatus",
    "OutboxService",
    "prefect_event_publisher",
]
