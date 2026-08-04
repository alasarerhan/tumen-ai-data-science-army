from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_workspace_member
from platform_api.core.config import settings
from platform_api.db.session import get_db
from platform_api.services.run_service import get_run_by_id_for_workspace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/runs", tags=["logs"])


async def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _mock_log_stream(run_id: str, run_status: str):
    """
    Yields SSE-formatted log lines for a given run.
    When Prefect integration is available replace this with real log polling.
    """
    lines = [
        {"ts": datetime.now(UTC).isoformat(), "level": "INFO", "msg": f"Starting run {run_id}…"},
        {"ts": datetime.now(UTC).isoformat(), "level": "INFO", "msg": "Initialising agents…"},
        {"ts": datetime.now(UTC).isoformat(), "level": "INFO", "msg": "Loading data sources…"},
        {
            "ts": datetime.now(UTC).isoformat(),
            "level": "INFO",
            "msg": "Running data cleaning agent…",
        },
        {
            "ts": datetime.now(UTC).isoformat(),
            "level": "INFO",
            "msg": "Running feature engineering agent…",
        },
        {"ts": datetime.now(UTC).isoformat(), "level": "INFO", "msg": "Running ML training agent…"},
        {
            "ts": datetime.now(UTC).isoformat(),
            "level": "INFO",
            "msg": "Evaluating model performance…",
        },
        {
            "ts": datetime.now(UTC).isoformat(),
            "level": "INFO",
            "msg": "Generating strategy report…",
        },
        {
            "ts": datetime.now(UTC).isoformat(),
            "level": "INFO",
            "msg": f"Run {run_id} finished with status: {run_status}",
        },
        {"ts": datetime.now(UTC).isoformat(), "level": "INFO", "msg": "__STREAM_END__"},
    ]
    for line in lines:
        yield await _sse_event(line)
        await asyncio.sleep(0.3)


@router.get("/{run_id}/logs")
async def stream_run_logs(
    run_id: str,
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    workspace = context["workspace"]
    run = get_run_by_id_for_workspace(db, run_id=run_id, workspace_id=workspace.id)

    # Try Prefect logs first; fall back to mock stream only for local verification.
    try:
        from platform_api.orchestration.prefect_gateway import (
            get_prefect_flow_run_logs,  # type: ignore[import]
        )

        async def prefect_stream():
            async for chunk in get_prefect_flow_run_logs(run.prefect_flow_run_id):
                yield await _sse_event(chunk)
            yield await _sse_event(
                {"ts": datetime.now(UTC).isoformat(), "level": "INFO", "msg": "__STREAM_END__"}
            )

        return StreamingResponse(prefect_stream(), media_type="text/event-stream")
    except (ImportError, AttributeError, Exception) as exc:
        if not (settings.is_local_profile() and settings.allow_local_run_fallback):
            logger.error("Prefect log stream unavailable and local fallback is disabled: %s", exc)
            raise HTTPException(status_code=503, detail="Run log stream is unavailable") from exc

    return StreamingResponse(
        _mock_log_stream(str(run.id), run.status),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
