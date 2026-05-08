"""Redis Streams-backed job queue for scheduled workflows.

This module implements a reliable job queue using Redis Streams with:
- Consumer groups for distributed processing
- Automatic retry with configurable max attempts
- Dead-letter queue for failed jobs
- Status tracking via Redis Sets

Best Practices Reference:
https://redis.io/tutorials/redis-backed-job-queue-for-background-workers

Usage
-----
::

    from platform_api.scheduler.job_queue import ScheduledJobQueue
    
    queue = ScheduledJobQueue(redis_url="redis://localhost:6379")
    
    # Enqueue a job
    job_id = queue.enqueue(
        workflow_id="wf-123",
        workflow_spec={"name": "My Workflow", "steps": [...]},
        schedule="0 9 * * *",
        tenant_id="tenant-1",
        workspace_id="ws-1",
    )
    
    # Claim and process a job
    job = queue.claim_job(consumer_name="worker-1")
    if job:
        # Process the job...
        queue.ack_job(job["id"], job["message_id"])
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from redis import Redis
from redis.commands.json.path import Path as JsonPath

from platform_api.core.config import settings

logger = logging.getLogger(__name__)


class RedisKeys:
    """Centralized Redis key management."""
    
    STREAM_SCHEDULED_JOBS = "workflow:scheduled:jobs"
    STREAM_DEAD_LETTER = "workflow:scheduled:dead"
    CONSUMER_GROUP = "workflow-workers"
    
    @staticmethod
    def job(job_id: str) -> str:
        return f"job:{job_id}"
    
    @staticmethod
    def status_set(status: str) -> str:
        return f"status:{status}"
    
    @staticmethod
    def workflow_jobs(workflow_id: str) -> str:
        return f"workflow:{workflow_id}:jobs"


class ScheduledJobQueue:
    """Redis Streams-backed job queue for scheduled workflows.
    
    This class implements a reliable job queue using Redis Streams with
    consumer groups, automatic retry, and dead-letter handling.
    
    Parameters
    ----------
    redis_url : str, optional
        Redis connection URL. Defaults to settings.agent_cache_redis_url.
    
    Attributes
    ----------
    redis : Redis
        Redis client instance.
    
    Example
    -------
    >>> queue = ScheduledJobQueue()
    >>> job_id = queue.enqueue(
    ...     workflow_id="wf-123",
    ...     workflow_spec={"name": "My Workflow"},
    ...     schedule="0 9 * * *",
    ...     tenant_id="tenant-1",
    ...     workspace_id="ws-1",
    ... )
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        url = redis_url or settings.agent_cache_redis_url
        if not url:
            raise ValueError(
                "Redis URL is required. Set AGENT_CACHE_REDIS_URL environment variable."
            )
        
        self.redis = Redis.from_url(url, decode_responses=True)
        self._ensure_consumer_group()
    
    def _ensure_consumer_group(self) -> None:
        """Ensure the consumer group exists for the stream."""
        try:
            self.redis.xgroup_create(
                name=RedisKeys.STREAM_SCHEDULED_JOBS,
                groupname=RedisKeys.CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            logger.info(
                "Created consumer group '%s' for stream '%s'",
                RedisKeys.CONSUMER_GROUP,
                RedisKeys.STREAM_SCHEDULED_JOBS,
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error("Failed to create consumer group: %s", e)
                raise
    
    def enqueue(
        self,
        workflow_id: str,
        workflow_spec: Dict[str, Any],
        schedule: str,
        tenant_id: str,
        workspace_id: str,
        max_attempts: int = 3,
        priority: str = "normal",
    ) -> str:
        """Add a scheduled job to the queue.
        
        Parameters
        ----------
        workflow_id : str
            Unique identifier for the workflow.
        workflow_spec : Dict[str, Any]
            The workflow specification.
        schedule : str
            Cron expression for the schedule.
        tenant_id : str
            Tenant identifier for multi-tenancy.
        workspace_id : str
            Workspace identifier.
        max_attempts : int, optional
            Maximum retry attempts. Defaults to 3.
        priority : str, optional
            Job priority: "high", "normal", "low". Defaults to "normal".
        
        Returns
        -------
        str
            The unique job ID.
        """
        job_id = str(uuid4())
        
        job_record = {
            "id": job_id,
            "workflow_id": workflow_id,
            "workflow_spec": workflow_spec,
            "schedule": schedule,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "status": "queued",
            "attempts": 0,
            "max_attempts": max_attempts,
            "priority": priority,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        self.redis.json().set(RedisKeys.job(job_id), JsonPath.root_path(), job_record)
        self.redis.sadd(RedisKeys.status_set("queued"), job_id)
        self.redis.sadd(RedisKeys.workflow_jobs(workflow_id), job_id)
        self.redis.xadd(RedisKeys.STREAM_SCHEDULED_JOBS, {"jobId": job_id})
        
        logger.info("Enqueued job %s for workflow %s", job_id, workflow_id)
        
        return job_id
    
    def claim_job(
        self,
        consumer_name: str,
        block_ms: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        """Claim a job from the queue for processing.
        
        Uses Redis Streams consumer groups to ensure each job is
        processed by exactly one consumer.
        
        Parameters
        ----------
        consumer_name : str
            Unique name for this consumer.
        block_ms : int, optional
            Milliseconds to block waiting for a job. Defaults to 1000.
        
        Returns
        -------
        Optional[Dict[str, Any]]
            The job record, or None if no job is available.
        """
        messages = self.redis.xreadgroup(
            groupname=RedisKeys.CONSUMER_GROUP,
            consumername=consumer_name,
            streams={RedisKeys.STREAM_SCHEDULED_JOBS: ">"},
            count=1,
            block=block_ms,
        )
        
        if not messages:
            return None
        
        stream_name, entries = messages[0]
        message_id, fields = entries[0]
        job_id = fields.get("jobId")
        
        if not job_id:
            logger.warning("Received message without jobId")
            self.redis.xack(
                RedisKeys.STREAM_SCHEDULED_JOBS,
                RedisKeys.CONSUMER_GROUP,
                message_id,
            )
            return None
        
        job = self.redis.json().get(RedisKeys.job(job_id))
        
        if job:
            job["message_id"] = message_id
            job["status"] = "processing"
            job["attempts"] += 1
            job["updated_at"] = datetime.utcnow().isoformat()
            
            self.redis.json().set(RedisKeys.job(job_id), JsonPath.root_path(), job)
            self.redis.srem(RedisKeys.status_set("queued"), job_id)
            self.redis.sadd(RedisKeys.status_set("processing"), job_id)
            
            logger.info("Claimed job %s (attempt %d)", job_id, job["attempts"])
        
        return job
    
    def ack_job(self, job_id: str, message_id: str) -> None:
        """Acknowledge successful job processing.
        
        Parameters
        ----------
        job_id : str
            The job ID.
        message_id : str
            The Redis Stream message ID.
        """
        self.redis.xack(
            RedisKeys.STREAM_SCHEDULED_JOBS,
            RedisKeys.CONSUMER_GROUP,
            message_id,
        )
        
        job = self.redis.json().get(RedisKeys.job(job_id))
        if job:
            job["status"] = "completed"
            job["updated_at"] = datetime.utcnow().isoformat()
            self.redis.json().set(RedisKeys.job(job_id), JsonPath.root_path(), job)
        
        self.redis.srem(RedisKeys.status_set("processing"), job_id)
        self.redis.sadd(RedisKeys.status_set("completed"), job_id)
        
        logger.info("Completed job %s", job_id)
    
    def retry_job(self, job_id: str, error: str) -> None:
        """Re-enqueue a failed job for retry.
        
        If the job has exceeded its max attempts, it will be moved
        to the dead-letter queue.
        
        Parameters
        ----------
        job_id : str
            The job ID.
        error : str
            The error message from the failed attempt.
        """
        job = self.redis.json().get(RedisKeys.job(job_id))
        
        if not job:
            logger.warning("Job %s not found for retry", job_id)
            return
        
        job["last_error"] = error
        job["updated_at"] = datetime.utcnow().isoformat()
        
        if job["attempts"] >= job["max_attempts"]:
            self._move_to_dead_letter(job, error)
        else:
            job["status"] = "retrying"
            self.redis.json().set(RedisKeys.job(job_id), JsonPath.root_path(), job)
            
            self.redis.srem(RedisKeys.status_set("processing"), job_id)
            self.redis.sadd(RedisKeys.status_set("retrying"), job_id)
            
            self.redis.xadd(RedisKeys.STREAM_SCHEDULED_JOBS, {"jobId": job_id})
            
            logger.info(
                "Re-enqueued job %s for retry (attempt %d/%d)",
                job_id,
                job["attempts"],
                job["max_attempts"],
            )
    
    def _move_to_dead_letter(self, job: Dict[str, Any], error: str) -> None:
        """Move a job to the dead-letter queue.
        
        Parameters
        ----------
        job : Dict[str, Any]
            The job record.
        error : str
            The final error message.
        """
        job_id = job["id"]
        
        job["status"] = "dead-letter"
        job["final_error"] = error
        job["dead_letter_at"] = datetime.utcnow().isoformat()
        
        self.redis.xadd(
            RedisKeys.STREAM_DEAD_LETTER,
            {
                "jobId": job_id,
                "reason": error,
                "attempts": str(job["attempts"]),
                "workflow_id": job.get("workflow_id", ""),
            },
        )
        
        self.redis.json().set(RedisKeys.job(job_id), JsonPath.root_path(), job)
        
        self.redis.srem(RedisKeys.status_set("processing"), job_id)
        self.redis.sadd(RedisKeys.status_set("dead-letter"), job_id)
        
        logger.warning("Moved job %s to dead-letter queue: %s", job_id, error)
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID.
        
        Parameters
        ----------
        job_id : str
            The job ID.
        
        Returns
        -------
        Optional[Dict[str, Any]]
            The job record, or None if not found.
        """
        return self.redis.json().get(RedisKeys.job(job_id))
    
    def get_jobs_by_status(self, status: str) -> list:
        """Get all job IDs with a specific status.
        
        Parameters
        ----------
        status : str
            The status to filter by.
        
        Returns
        -------
        list
            List of job IDs.
        """
        return list(self.redis.smembers(RedisKeys.status_set(status)))
    
    def get_dead_letter_jobs(self, limit: int = 100) -> list:
        """Get jobs from the dead-letter queue.
        
        Parameters
        ----------
        limit : int, optional
            Maximum number of jobs to return. Defaults to 100.
        
        Returns
        -------
        list
            List of dead-letter job records.
        """
        job_ids = self.get_jobs_by_status("dead-letter")[:limit]
        jobs = []
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job:
                jobs.append(job)
        return jobs
    
    def requeue_dead_letter_job(self, job_id: str) -> bool:
        """Re-queue a job from the dead-letter queue.
        
        Parameters
        ----------
        job_id : str
            The job ID to re-queue.
        
        Returns
        -------
        bool
            True if the job was re-queued, False if not found.
        """
        job = self.get_job(job_id)
        
        if not job or job.get("status") != "dead-letter":
            return False
        
        job["status"] = "queued"
        job["attempts"] = 0
        job["updated_at"] = datetime.utcnow().isoformat()
        del job["final_error"]
        del job["dead_letter_at"]
        
        self.redis.json().set(RedisKeys.job(job_id), JsonPath.root_path(), job)
        
        self.redis.srem(RedisKeys.status_set("dead-letter"), job_id)
        self.redis.sadd(RedisKeys.status_set("queued"), job_id)
        
        self.redis.xadd(RedisKeys.STREAM_SCHEDULED_JOBS, {"jobId": job_id})
        
        logger.info("Re-queued dead-letter job %s", job_id)
        
        return True
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics.
        
        Returns
        -------
        Dict[str, int]
            Dictionary with counts for each status.
        """
        return {
            "queued": len(self.get_jobs_by_status("queued")),
            "processing": len(self.get_jobs_by_status("processing")),
            "retrying": len(self.get_jobs_by_status("retrying")),
            "completed": len(self.get_jobs_by_status("completed")),
            "dead_letter": len(self.get_jobs_by_status("dead-letter")),
        }

    def purge_tenant_data(self, tenant_id: str) -> Dict[str, int]:
        """Delete all Redis-backed scheduled-job data for a tenant."""
        job_ids_to_delete: list[str] = []
        workflow_ids_to_touch: set[str] = set()

        for job_key in self.redis.scan_iter(match="job:*"):
            job = self.redis.json().get(job_key)
            if not job or str(job.get("tenant_id")) != str(tenant_id):
                continue
            job_ids_to_delete.append(str(job["id"]))
            workflow_id = job.get("workflow_id")
            if workflow_id:
                workflow_ids_to_touch.add(str(workflow_id))

        if not job_ids_to_delete:
            return {"jobs_deleted": 0, "stream_entries_deleted": 0}

        deleted_stream_entries = 0
        job_ids_set = set(job_ids_to_delete)

        for status in ("queued", "processing", "retrying", "completed", "dead-letter"):
            status_key = RedisKeys.status_set(status)
            if job_ids_to_delete:
                self.redis.srem(status_key, *job_ids_to_delete)

        for workflow_id in workflow_ids_to_touch:
            self.redis.srem(RedisKeys.workflow_jobs(workflow_id), *job_ids_to_delete)

        for job_id in job_ids_to_delete:
            self.redis.delete(RedisKeys.job(job_id))

        for stream_name in (RedisKeys.STREAM_SCHEDULED_JOBS, RedisKeys.STREAM_DEAD_LETTER):
            pending_ids: list[str] = []
            to_delete: list[str] = []
            for message_id, fields in self.redis.xrange(stream_name):
                if fields.get("jobId") in job_ids_set:
                    pending_ids.append(message_id)
                    to_delete.append(message_id)
            if pending_ids and stream_name == RedisKeys.STREAM_SCHEDULED_JOBS:
                try:
                    self.redis.xack(
                        RedisKeys.STREAM_SCHEDULED_JOBS,
                        RedisKeys.CONSUMER_GROUP,
                        *pending_ids,
                    )
                except Exception:
                    logger.debug("No pending scheduled-job stream entries to ack during tenant purge")
            if to_delete:
                self.redis.xdel(stream_name, *to_delete)
                deleted_stream_entries += len(to_delete)

        logger.info(
            "Purged scheduled job data for tenant %s: jobs=%d stream_entries=%d",
            tenant_id,
            len(job_ids_to_delete),
            deleted_stream_entries,
        )
        return {
            "jobs_deleted": len(job_ids_to_delete),
            "stream_entries_deleted": deleted_stream_entries,
        }
