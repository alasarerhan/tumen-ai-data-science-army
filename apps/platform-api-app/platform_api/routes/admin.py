"""Admin endpoints for system monitoring and management.

Provides endpoints for:
- DLQ management (view, replay)
- Queue statistics
- Scheduler status
- Memory monitoring
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_tenant_admin
from platform_api.db.session import get_db
from platform_api.services.runtime_engine_parity_service import build_runtime_engine_parity_report

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class DlqEventResponse(BaseModel):
    id: str
    original_event_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str | None
    final_error: str | None
    retry_count: int
    original_created_at: str
    moved_to_dlq_at: str
    reviewed: bool
    reviewed_at: str | None
    resolution_note: str | None


class QueueStatsResponse(BaseModel):
    pending: int
    processing: int
    failed: int
    dlq: int


class SchedulerJobResponse(BaseModel):
    job_name: str
    job_type: str
    enabled: bool
    last_run_at: str | None
    next_run_at: str | None
    last_run_status: str | None


class SchedulerStatusResponse(BaseModel):
    is_leader: bool
    leader_id: str | None
    jobs: list[SchedulerJobResponse] = Field(default_factory=list)
    restricted: bool = False
    message: str | None = None


class MemoryStatsResponse(BaseModel):
    rss_bytes: int
    vms_bytes: int
    percent: float
    available_system_memory: int
    total_system_memory: int
    growth_rate_bytes_per_minute: float
    recommendations: list[str]


@router.get("/dlq")
async def list_dlq_events(
    unreviewed_only: bool = True,
    context: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List events in the Dead Letter Queue (admin only)."""
    from platform_api.services.outbox import OutboxService

    outbox = OutboxService(db)
    events = outbox.get_dlq_events(
        limit=100,
        unreviewed_only=unreviewed_only,
        tenant_id=context["tenant_id"],
    )

    return {
        "items": [
            {
                "id": str(e.id),
                "original_event_id": str(e.original_event_id),
                "aggregate_type": e.aggregate_type,
                "aggregate_id": e.aggregate_id,
                "event_type": e.event_type,
                "payload_json": e.payload_json,
                "final_error": e.final_error,
                "retry_count": e.retry_count,
                "original_created_at": e.original_created_at.isoformat()
                if e.original_created_at
                else None,
                "moved_to_dlq_at": e.moved_to_dlq_at.isoformat() if e.moved_to_dlq_at else None,
                "reviewed": e.reviewed,
                "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
                "resolution_note": e.resolution_note,
            }
            for e in events
        ]
    }


@router.post("/dlq/{event_id}/replay")
async def replay_dlq_event(
    event_id: str,
    context: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Replay a failed event from the DLQ (admin only)."""
    import uuid

    from platform_api.services.outbox import OutboxService

    dlq_id = uuid.UUID(event_id)

    outbox = OutboxService(db)
    try:
        new_event = outbox.replay_dlq_event(
            dlq_id,
            tenant_id=context["tenant_id"],
            reviewed_by_user_id=context["user"].id,
        )
    except ValueError:
        return {"status": "not_found", "new_event_id": None}

    return {
        "status": "replayed",
        "new_event_id": str(new_event.id),
    }


@router.get("/queue-stats", response_model=QueueStatsResponse)
async def get_queue_stats(
    context: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get outbox queue statistics (admin only)."""
    from platform_api.services.outbox import OutboxService

    outbox = OutboxService(db)
    stats = outbox.get_queue_stats(tenant_id=context["tenant_id"])

    return stats


@router.get("/scheduler", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    _context: dict = Depends(require_tenant_admin),
) -> dict:
    """Get scheduler status metadata without exposing platform internals."""
    return {
        "is_leader": False,
        "leader_id": None,
        "jobs": [],
        "restricted": True,
        "message": "Scheduler status is restricted to platform operators.",
    }


@router.get("/runtime-engine/parity")
async def get_runtime_engine_parity_report(
    _context: dict = Depends(require_tenant_admin),
) -> dict:
    """Run a deterministic RuntimeEngine parity harness for tenant admins."""
    return build_runtime_engine_parity_report()


@router.get("/memory", response_model=MemoryStatsResponse)
async def get_memory_stats(
    _context: dict = Depends(require_tenant_admin),
) -> dict:
    """Get process memory statistics (admin only)."""
    from platform_api.services.memory_monitor import get_memory_monitor

    monitor = get_memory_monitor()
    stats = monitor.get_memory_stats()
    recommendations = monitor.get_recommendations()
    growth_rate = monitor.get_memory_growth_rate()

    return {
        "rss_bytes": stats.get("rss_bytes", 0),
        "vms_bytes": stats.get("vms_bytes", 0),
        "percent": stats.get("percent", 0.0),
        "available_system_memory": stats.get("available_system_memory", 0),
        "total_system_memory": stats.get("total_system_memory", 0),
        "growth_rate_bytes_per_minute": growth_rate,
        "recommendations": recommendations,
    }
