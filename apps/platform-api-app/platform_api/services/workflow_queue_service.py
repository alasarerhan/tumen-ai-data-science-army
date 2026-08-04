from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from platform_api.core.config import settings
from platform_api.core.service_errors import UpstreamUnavailableError

logger = logging.getLogger(__name__)

WORKFLOW_RUN_QUEUE_KEY = "workflow-runs:queued"


def enqueue_workflow_run(
    *,
    run_id: uuid.UUID | str,
    workspace_id: uuid.UUID | str,
    tenant_id: uuid.UUID | str,
    workflow_spec_id: uuid.UUID | str | None,
    trigger_type: str | None,
) -> dict[str, Any]:
    """Queue a workflow run for worker execution when Redis is configured.

    Existing Prefect/local orchestration paths remain compatible while the worker
    runtime is introduced behind the Redis queue boundary.
    """
    redis_url = settings.workflow_queue_redis_url.strip() or settings.agent_cache_redis_url.strip()
    if not redis_url:
        if settings.workflow_queue_required:
            raise UpstreamUnavailableError(
                "Workflow queue Redis URL is required but not configured"
            )
        return {"enqueued": False, "queue": None, "reason": "workflow_queue_not_configured"}

    try:
        from redis import Redis
    except Exception as exc:  # pragma: no cover - import depends on optional runtime package
        if settings.workflow_queue_required:
            raise UpstreamUnavailableError("Redis package is required for workflow queue") from exc
        logger.warning("Redis package unavailable; workflow run was not queued", exc_info=True)
        return {"enqueued": False, "queue": None, "reason": "redis_package_unavailable"}

    payload = {
        "run_id": str(run_id),
        "workspace_id": str(workspace_id),
        "tenant_id": str(tenant_id),
        "workflow_spec_id": str(workflow_spec_id) if workflow_spec_id else None,
        "trigger_type": trigger_type or "manual",
    }
    try:
        redis = Redis.from_url(redis_url, decode_responses=True)
        message_id = redis.xadd(WORKFLOW_RUN_QUEUE_KEY, {"payload": json.dumps(payload)})
    except Exception as exc:
        if settings.workflow_queue_required:
            raise UpstreamUnavailableError("Failed to enqueue workflow run") from exc
        logger.warning("Failed to enqueue workflow run", exc_info=True)
        return {
            "enqueued": False,
            "queue": WORKFLOW_RUN_QUEUE_KEY,
            "reason": "redis_enqueue_failed",
        }
    return {"enqueued": True, "queue": WORKFLOW_RUN_QUEUE_KEY, "message_id": str(message_id)}
