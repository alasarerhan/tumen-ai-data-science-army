"""API routes for scheduler job queue and schedule parsing."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from platform_api.authz.dependencies import require_workspace_admin, require_workspace_member
from platform_api.scheduler.job_queue import ScheduledJobQueue
from platform_api.scheduler.schedule_parser import ScheduleParser

router = APIRouter(prefix="/v1/scheduler", tags=["scheduler"])


def _job_belongs_to_workspace(job: dict[str, Any], workspace_id: str, tenant_id: str) -> bool:
    return str(job.get("workspace_id")) == workspace_id and str(job.get("tenant_id")) == tenant_id


def _scoped_queue_stats(
    queue: ScheduledJobQueue, workspace_id: str, tenant_id: str
) -> dict[str, int]:
    stats: dict[str, int] = {}
    for status, response_key in (
        ("queued", "queued"),
        ("processing", "processing"),
        ("retrying", "retrying"),
        ("completed", "completed"),
        ("dead-letter", "dead_letter"),
    ):
        count = 0
        for job_id in queue.get_jobs_by_status(status):
            job = queue.get_job(job_id)
            if job and _job_belongs_to_workspace(job, workspace_id, tenant_id):
                count += 1
        stats[response_key] = count
    return stats


class ParseScheduleRequest(BaseModel):
    expression: str


class EnqueueJobRequest(BaseModel):
    workflow_id: str
    workflow_spec: dict[str, Any]
    schedule: str
    max_attempts: int = 3
    priority: str = "normal"


@router.post("/parse")
async def parse_schedule(
    body: ParseScheduleRequest,
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    parser = ScheduleParser()
    try:
        cron, description = parser.parse_with_description(body.expression)
        return {
            "cron": cron,
            "description": description,
            "original": body.expression,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/jobs", status_code=201)
async def enqueue_job(
    body: EnqueueJobRequest,
    context: dict = Depends(require_workspace_admin),
) -> dict[str, Any]:
    workspace = context["workspace"]

    try:
        queue = ScheduledJobQueue()
        job_id = queue.enqueue(
            workflow_id=body.workflow_id,
            workflow_spec=body.workflow_spec,
            schedule=body.schedule,
            tenant_id=str(workspace.tenant_id),
            workspace_id=str(workspace.id),
            max_attempts=body.max_attempts,
            priority=body.priority,
        )
        return {
            "job_id": job_id,
            "status": "queued",
            "workflow_id": body.workflow_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    workspace = context["workspace"]
    queue = ScheduledJobQueue()
    job = queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not _job_belongs_to_workspace(job, str(workspace.id), str(workspace.tenant_id)):
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    workspace = context["workspace"]
    queue = ScheduledJobQueue()

    if status:
        job_ids = queue.get_jobs_by_status(status)
    else:
        stats = _scoped_queue_stats(queue, str(workspace.id), str(workspace.tenant_id))
        return {
            "stats": stats,
            "jobs": [],
        }

    jobs = []
    for job_id in job_ids[:50]:
        job = queue.get_job(job_id)
        if job and _job_belongs_to_workspace(job, str(workspace.id), str(workspace.tenant_id)):
            jobs.append(job)

    return {"jobs": jobs}


@router.get("/stats")
async def get_queue_stats(
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    workspace = context["workspace"]
    queue = ScheduledJobQueue()
    return _scoped_queue_stats(queue, str(workspace.id), str(workspace.tenant_id))


@router.post("/jobs/{job_id}/requeue", status_code=200)
async def requeue_job(
    job_id: str,
    context: dict = Depends(require_workspace_admin),
) -> dict[str, Any]:
    workspace = context["workspace"]
    queue = ScheduledJobQueue()
    job = queue.get_job(job_id)
    if not job or not _job_belongs_to_workspace(job, str(workspace.id), str(workspace.tenant_id)):
        raise HTTPException(status_code=404, detail="Job not found or not in dead-letter queue")
    success = queue.requeue_dead_letter_job(job_id)

    if not success:
        raise HTTPException(status_code=404, detail="Job not found or not in dead-letter queue")

    return {"job_id": job_id, "status": "requeued"}


@router.get("/dead-letter")
async def list_dead_letter_jobs(
    limit: int = 50,
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    workspace = context["workspace"]
    queue = ScheduledJobQueue()
    jobs = [
        job
        for job in queue.get_dead_letter_jobs(limit=limit)
        if _job_belongs_to_workspace(job, str(workspace.id), str(workspace.tenant_id))
    ]
    return {"jobs": jobs}
