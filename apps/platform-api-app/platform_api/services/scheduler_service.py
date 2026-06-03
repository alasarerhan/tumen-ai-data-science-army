"""Scheduler service for background jobs with leader election.

Implements distributed scheduling with:
* Leader election via database lock (prevents double execution)
* Configurable cron or interval-based scheduling
* Automatic failover when leader crashes
* Prometheus metrics for monitoring

Best Practices Reference:
https://docs-3.prefect.io/v3/how-to-guides/deployments/manage-schedules
https://microservices.io/patterns/data/saga.html

Usage
-----
::

    from platform_api.services.scheduler_service import SchedulerService

    scheduler = SchedulerService(db)

    # Register a job
    scheduler.register_job(
        job_name="artifact_cleanup",
        job_type="cleanup",
        interval_seconds=3600,  # Every hour
        handler=cleanup_expired_artifacts,
    )

    # Start the scheduler (typically in FastAPI lifespan)
    await scheduler.start()

    # Stop gracefully (in shutdown)
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable, Dict, Optional

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import ScheduledJob
from platform_api.tenant_context import system_actor_context

logger = logging.getLogger(__name__)


SCHEDULER_JOBS_TOTAL = Counter(
    "platform_api_scheduler_jobs_total",
    "Total number of scheduled job executions",
    ["job_name", "status"],
    registry=None,
)

SCHEDULER_JOB_DURATION = Histogram(
    "platform_api_scheduler_job_duration_seconds",
    "Duration of scheduled job executions",
    ["job_name"],
    registry=None,
)

SCHEDULER_LEADER_GAUGE = Gauge(
    "platform_api_scheduler_is_leader",
    "Whether this instance is the scheduler leader (1=leader, 0=follower)",
    registry=None,
)

SCHEDULER_QUEUE_DEPTH = Gauge(
    "platform_api_scheduler_queue_depth",
    "Number of pending scheduled jobs",
    registry=None,
)

SCHEDULER_STUCK_JOBS_GAUGE = Gauge(
    "platform_api_scheduler_stuck_jobs",
    "Number of jobs stuck in 'running' state",
    registry=None,
)

SCHEDULER_RUNNING_JOBS_GAUGE = Gauge(
    "platform_api_scheduler_running_jobs",
    "Number of scheduled jobs currently executing on this instance",
    registry=None,
)


MIN_INTERVAL_SECONDS = 1
MIN_LEADER_TTL_SECONDS = 10
MAX_LEADER_TTL_SECONDS = 3600
STUCK_JOB_THRESHOLD_SECONDS = 3600


class SchedulerService:
    """Distributed scheduler service with leader election.

    Uses database-based leader election to ensure only one instance
    runs scheduled jobs in a multi-replica deployment.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session.
    leader_ttl_seconds : int
        How long leader lock is valid before expiring (default: 60).
        Must be at least 10 seconds to prevent thrashing.
    poll_interval_seconds : float
        How often to check for jobs to run (default: 5.0).
        Must be at least 1.0 second.
    """

    def __init__(
        self,
        db: Session,
        leader_ttl_seconds: int = 60,
        poll_interval_seconds: float = 5.0,
        max_concurrent_jobs: int | None = None,
    ) -> None:
        if leader_ttl_seconds < MIN_LEADER_TTL_SECONDS:
            raise ValueError(
                f"leader_ttl_seconds must be at least {MIN_LEADER_TTL_SECONDS} seconds "
                f"to prevent leader thrashing, got {leader_ttl_seconds}"
            )
        if leader_ttl_seconds > MAX_LEADER_TTL_SECONDS:
            raise ValueError(
                f"leader_ttl_seconds must be at most {MAX_LEADER_TTL_SECONDS} seconds, "
                f"got {leader_ttl_seconds}"
            )
        if poll_interval_seconds < 1.0:
            raise ValueError(
                f"poll_interval_seconds must be at least 1.0 second, got {poll_interval_seconds}"
            )
        resolved_max_concurrent_jobs = (
            settings.scheduler_max_concurrent_jobs
            if max_concurrent_jobs is None
            else max_concurrent_jobs
        )
        if resolved_max_concurrent_jobs < 1:
            raise ValueError("max_concurrent_jobs must be at least 1")
        
        self._db = db
        self._leader_ttl = leader_ttl_seconds
        self._poll_interval = poll_interval_seconds
        self._max_concurrent_jobs = resolved_max_concurrent_jobs
        self._leader_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._handlers: Dict[str, Callable] = {}
        self._job_timeouts: Dict[str, int] = {}
        self._is_leader = False
        self._active_tasks: set = set()

    def register_job(
        self,
        job_name: str,
        job_type: str,
        handler: Callable,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        enabled: bool = True,
        stuck_timeout_seconds: Optional[int] = None,
    ) -> ScheduledJob:
        """Register or update a scheduled job.

        Parameters
        ----------
        job_name : str
            Unique name for the job.
        job_type : str
            Type of job (e.g., "cleanup", "sync", "report").
        handler : callable
            Async or sync function to execute.
        cron_expression : str | None
            Cron expression for scheduling (e.g., "0 * * * *").
        interval_seconds : int | None
            Interval in seconds (alternative to cron). Must be >= 1.
        enabled : bool
            Whether the job is enabled.
        stuck_timeout_seconds : int | None
            Custom timeout for detecting stuck jobs. If a job runs longer than
            this, it will be marked as failed and recovered. Defaults to
            STUCK_JOB_THRESHOLD_SECONDS (3600 seconds = 1 hour).

        Returns
        -------
        ScheduledJob
            The registered job record.
        
        Raises
        ------
        ValueError
            If interval_seconds is less than MIN_INTERVAL_SECONDS.
        """
        if interval_seconds is not None and interval_seconds < MIN_INTERVAL_SECONDS:
            raise ValueError(
                f"interval_seconds must be at least {MIN_INTERVAL_SECONDS} second(s), "
                f"got {interval_seconds}"
            )
        
        if not job_name or not job_name.strip():
            raise ValueError("job_name cannot be empty")
        
        if not job_type or not job_type.strip():
            raise ValueError("job_type cannot be empty")
        
        self._handlers[job_name] = handler
        self._job_timeouts[job_name] = stuck_timeout_seconds or STUCK_JOB_THRESHOLD_SECONDS

        job = self._db.execute(
            select(ScheduledJob).where(ScheduledJob.job_name == job_name)
        ).scalar_one_or_none()

        now = datetime.now(UTC)

        if job:
            job.job_type = job_type
            job.cron_expression = cron_expression
            job.interval_seconds = interval_seconds
            job.enabled = enabled
            if not job.next_run_at:
                job.next_run_at = self._calculate_next_run(
                    cron_expression, interval_seconds, now
                )
        else:
            next_run = self._calculate_next_run(cron_expression, interval_seconds, now)
            job = ScheduledJob(
                job_name=job_name,
                job_type=job_type,
                cron_expression=cron_expression,
                interval_seconds=interval_seconds,
                enabled=enabled,
                next_run_at=next_run,
            )
            self._db.add(job)

        self._db.flush()
        logger.info(
            "Registered scheduled job: name=%s, type=%s, next_run=%s",
            job_name, job_type, job.next_run_at,
        )
        return job

    def _calculate_next_run(
        self,
        cron_expression: Optional[str],
        interval_seconds: Optional[int],
        from_time: datetime,
    ) -> datetime:
        """Calculate the next run time for a job."""
        if interval_seconds:
            return from_time + timedelta(seconds=interval_seconds)
        elif cron_expression:
            try:
                from croniter import croniter
                cron = croniter(cron_expression, from_time)
                return cron.get_next(datetime)
            except ImportError:
                logger.warning("croniter not installed, using interval fallback")
                return from_time + timedelta(hours=1)
        else:
            return from_time + timedelta(hours=1)

    async def _try_acquire_leadership(self) -> bool:
        """Try to acquire or renew leadership.

        Returns
        -------
        bool
            True if this instance is now the leader.
        """
        now = datetime.now(UTC)
        expiry = now + timedelta(seconds=self._leader_ttl)

        result = self._db.execute(
            update(ScheduledJob)
            .where(
                (ScheduledJob.enabled == True),
                (
                    (ScheduledJob.leader_id == None) |
                    (ScheduledJob.leader_id == self._leader_id) |
                    (ScheduledJob.leader_expires_at < now)
                )
            )
            .values(leader_id=self._leader_id, leader_expires_at=expiry)
            .returning(ScheduledJob.id)
        )
        acquired = result.first() is not None
        self._db.commit()

        if acquired:
            self._is_leader = True
            SCHEDULER_LEADER_GAUGE.set(1)
            return True

        self._is_leader = False
        SCHEDULER_LEADER_GAUGE.set(0)
        return False

    async def _release_leadership(self) -> None:
        """Release leadership gracefully."""
        try:
            self._db.execute(
                update(ScheduledJob)
                .where(ScheduledJob.leader_id == self._leader_id)
                .values(leader_id=None, leader_expires_at=None)
            )
            self._db.commit()
            self._is_leader = False
            SCHEDULER_LEADER_GAUGE.set(0)
            logger.info("Released scheduler leadership")
        except Exception as e:
            logger.error("Failed to release leadership: %s", e)

    async def _run_job(self, job: ScheduledJob) -> None:
        """Execute a scheduled job by ID using an isolated status session."""
        self._db.commit()
        await self._run_job_by_id(job.id)

    async def _run_job_by_id(self, job_id: uuid.UUID) -> None:
        """Execute a scheduled job with isolated DB sessions."""
        from platform_api.db.session import SessionLocal

        status_db = SessionLocal()
        job = status_db.get(ScheduledJob, job_id)
        if job is None:
            status_db.close()
            logger.warning("Scheduled job disappeared before execution: %s", job_id)
            return

        job_name = job.job_name
        handler = self._handlers.get(job_name)

        if not handler:
            status_db.close()
            logger.warning("No handler registered for job: %s", job_name)
            return

        start_time = datetime.now(UTC)
        job.last_run_at = start_time
        job.last_run_status = "running"
        status_db.add(job)
        status_db.commit()

        job_db = SessionLocal()
        try:
            logger.info("Running scheduled job: %s", job_name)

            with system_actor_context(job_db):
                if asyncio.iscoroutinefunction(handler):
                    task = asyncio.create_task(handler(job_db))
                    self._active_tasks.add(task)
                    task.add_done_callback(lambda t: self._active_tasks.discard(t))
                    try:
                        await asyncio.wait_for(
                            task,
                            timeout=settings.scheduler_job_timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        raise
                else:
                    await asyncio.wait_for(
                        asyncio.to_thread(handler, job_db),
                        timeout=settings.scheduler_job_timeout_seconds,
                    )

            job_db.commit()
            job.last_run_status = "success"
            job.last_run_error = None
            SCHEDULER_JOBS_TOTAL.labels(job_name=job_name, status="success").inc()
            logger.info("Job completed successfully: %s", job_name)

        except asyncio.TimeoutError:
            job.last_run_status = "timeout"
            job.last_run_error = f"Job timed out after {settings.scheduler_job_timeout_seconds} seconds"
            SCHEDULER_JOBS_TOTAL.labels(job_name=job_name, status="timeout").inc()
            logger.error("Job timed out: %s after %ds", job_name, settings.scheduler_job_timeout_seconds)
        except Exception as e:
            job.last_run_status = "failed"
            job.last_run_error = str(e)[:1000]
            SCHEDULER_JOBS_TOTAL.labels(job_name=job_name, status="failed").inc()
            logger.error("Job failed: %s, error: %s", job_name, e)

        finally:
            job_db.close()
            duration = (datetime.now(UTC) - start_time).total_seconds()
            SCHEDULER_JOB_DURATION.labels(job_name=job_name).observe(duration)

            job = status_db.get(ScheduledJob, job_id)
            if job is None:
                status_db.close()
                return
            job.next_run_at = self._calculate_next_run(
                job.cron_expression,
                job.interval_seconds,
                datetime.now(UTC),
            )
            status_db.add(job)
            status_db.commit()
            status_db.close()

    async def _run_job_with_limit(self, semaphore: asyncio.Semaphore, job_id: uuid.UUID) -> None:
        async with semaphore:
            SCHEDULER_RUNNING_JOBS_GAUGE.inc()
            try:
                await self._run_job_by_id(job_id)
            finally:
                SCHEDULER_RUNNING_JOBS_GAUGE.dec()

    async def _recover_stuck_jobs(self) -> int:
        """Recover jobs stuck in 'running' state.
        
        Jobs that have been in 'running' state for longer than
        STUCK_JOB_THRESHOLD_SECONDS are reset to 'failed'.
        
        Returns
        -------
        int
            Number of jobs recovered.
        """
        now = datetime.now(UTC)
        threshold = now - timedelta(seconds=STUCK_JOB_THRESHOLD_SECONDS)
        
        stuck_jobs = list(
            self._db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.last_run_status == "running",
                    ScheduledJob.last_run_at < threshold,
                )
            ).scalars()
        )
        
        recovered = 0
        for job in stuck_jobs:
            job.last_run_status = "failed"
            job.last_run_error = f"Job recovered after being stuck for >{STUCK_JOB_THRESHOLD_SECONDS}s"
            job.next_run_at = self._calculate_next_run(
                job.cron_expression,
                job.interval_seconds,
                now,
            )
            self._db.add(job)
            recovered += 1
            logger.warning(
                "Recovered stuck job: %s (was running since %s)",
                job.job_name, job.last_run_at,
            )
        
        if recovered > 0:
            self._db.commit()
            SCHEDULER_STUCK_JOBS_GAUGE.set(recovered)
        
        return recovered

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Scheduler loop started")

        while self._running:
            try:
                is_leader = await self._try_acquire_leadership()

                if is_leader:
                    await self._recover_stuck_jobs()

                    now = datetime.now(UTC)

                    due_job_ids = [
                        row[0]
                        for row in self._db.execute(
                            select(ScheduledJob.id)
                            .where(
                                ScheduledJob.enabled == True,
                                ScheduledJob.next_run_at <= now,
                                or_(
                                    ScheduledJob.last_run_status == None,
                                    ScheduledJob.last_run_status != "running",
                                ),
                            )
                        ).all()
                    ]

                    SCHEDULER_QUEUE_DEPTH.set(len(due_job_ids))

                    semaphore = asyncio.Semaphore(self._max_concurrent_jobs)
                    tasks = {
                        asyncio.create_task(self._run_job_with_limit(semaphore, job_id))
                        for job_id in due_job_ids
                    }
                    self._active_tasks.update(tasks)
                    for task in tasks:
                        task.add_done_callback(lambda t: self._active_tasks.discard(t))

                    if tasks:
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                        for result in results:
                            if isinstance(result, Exception):
                                logger.error("Job execution error: %s", result)

                await asyncio.sleep(self._poll_interval)

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)
                await asyncio.sleep(self._poll_interval * 2)

        await self._release_leadership()
        logger.info("Scheduler loop stopped")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started with leader_id=%s", self._leader_id)

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        for active_task in list(self._active_tasks):
            active_task.cancel()
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()

        await self._release_leadership()
        logger.info("Scheduler stopped")

    @property
    def is_leader(self) -> bool:
        """Check if this instance is the current leader."""
        return self._is_leader


def create_default_scheduler(db: Session) -> SchedulerService:
    """Create a scheduler with default jobs registered.

    Parameters
    ----------
    db : Session
        Database session.

    Returns
    -------
    SchedulerService
        Configured scheduler with default jobs.
    """
    from platform_api.services.artifact_cleanup_service import cleanup_expired_artifacts

    scheduler = SchedulerService(db)

    scheduler.register_job(
        job_name="artifact_cleanup",
        job_type="cleanup",
        handler=lambda session: cleanup_expired_artifacts(session, dry_run=False),
        interval_seconds=settings.artifact_cleanup_interval_seconds,
        enabled=True,
    )

    scheduler.register_job(
        job_name="outbox_processor",
        job_type="outbox",
        handler=_process_outbox_job,
        interval_seconds=5,
        enabled=True,
    )

    scheduler.register_job(
        job_name="dlq_monitor",
        job_type="monitoring",
        handler=_monitor_dlq_job,
        interval_seconds=60,
        enabled=True,
    )

    return scheduler


async def _process_outbox_job(db: Session) -> None:
    """Process pending outbox events."""
    from platform_api.services.outbox import OutboxService, prefect_event_publisher

    outbox = OutboxService(db)
    stats = await outbox.process_pending_events(
        publisher=prefect_event_publisher,
        batch_size=10,
    )

    if stats["published"] > 0 or stats["dlq"] > 0:
        logger.info(
            "Outbox processing: published=%d, retried=%d, failed=%d, dlq=%d",
            stats["published"], stats["retried"], stats["failed"], stats["dlq"],
        )


async def _monitor_dlq_job(db: Session) -> None:
    """Monitor DLQ and alert on threshold breach."""
    from platform_api.services.outbox import OutboxService

    outbox = OutboxService(db)
    stats = outbox.get_queue_stats()

    dlq_threshold = settings.dlq_alert_threshold

    if stats["dlq"] >= dlq_threshold:
        logger.error(
            "DLQ ALERT: %d events in DLQ (threshold=%d)",
            stats["dlq"], dlq_threshold,
        )

    outbox.update_metrics()


__all__ = [
    "SchedulerService",
    "create_default_scheduler",
    "SCHEDULER_JOBS_TOTAL",
    "SCHEDULER_JOB_DURATION",
    "SCHEDULER_LEADER_GAUGE",
    "SCHEDULER_QUEUE_DEPTH",
    "SCHEDULER_STUCK_JOBS_GAUGE",
    "SCHEDULER_RUNNING_JOBS_GAUGE",
]
