"""Signal streaming endpoints with SSE and replay support.

Implements Server-Sent Events (SSE) with:
* Last-Event-ID header for reconnection replay
* Sequential event IDs for reliable ordering
* Automatic reconnection handling

Best Practices Reference:
https://http.dev/last-event-id
https://ithy.com/article/sse-streaming-retries-v0p7rdp1
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.core.config import settings
from platform_api.db.session import get_db
from platform_api.services.identity_service import get_or_create_user
from platform_api.services.run_service import get_workspace_for_member
from platform_api.services.signal_service import (
    emit_signal,
    ensure_run_for_workspace,
    list_signals,
    signal_to_dict,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/runs", tags=["signals"])


class EmitSignalRequest(BaseModel):
    workspace_id: str
    signal_type: str = Field(min_length=1, max_length=30)
    target_step: str | None = Field(default=None, max_length=150)
    note: str | None = Field(default=None, max_length=4000)
    payload: dict = Field(default_factory=dict)


@router.post("/{run_id}/signals", status_code=201)
async def create_signal(
    run_id: str,
    body: EmitSignalRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    workspace = get_workspace_for_member(db, workspace_id=body.workspace_id, user_id=user.id)
    run = ensure_run_for_workspace(db, run_id=run_id, workspace_id=workspace.id)

    event = emit_signal(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        signal_type=body.signal_type,
        target_step=body.target_step,
        note=body.note,
        payload=body.payload,
        created_by_user_id=user.id,
    )
    db.commit()
    db.refresh(event)
    return signal_to_dict(event)


@router.get("/{run_id}/signals")
async def get_signals(
    run_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    user = get_or_create_user(db, principal)
    workspace = get_workspace_for_member(db, workspace_id=workspace_id, user_id=user.id)
    run = ensure_run_for_workspace(db, run_id=run_id, workspace_id=workspace.id)
    events = list_signals(db, workflow_run_id=run.id, limit=200)
    return {"items": [signal_to_dict(e) for e in events]}


@router.get("/{run_id}/signals/stream")
async def stream_signals(
    run_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
    last_event_id: str | None = Query(
        default=None,
        alias="last_event_id",
        description="ID of last received event for reconnection replay",
    ),
    last_event_id_header: str | None = Header(
        default=None,
        alias="Last-Event-ID",
        description="Last-Event-ID header for SSE reconnection",
    ),
) -> StreamingResponse:
    """Stream signals with SSE and reconnection support.

    Reconnection Pattern:
    1. Client connects with Last-Event-ID header or query param
    2. Server replays all events after that ID
    3. Server continues streaming new events
    4. If connection drops, client reconnects with last received ID

    Best Practices:
    - Use Last-Event-ID header (standard SSE)
    - Fallback to query param for compatibility
    - Include event ID in each SSE message
    - Handle missing events gracefully (may have been cleaned up)

    Reference: https://http.dev/last-event-id
    """
    user = get_or_create_user(db, principal)
    workspace = get_workspace_for_member(db, workspace_id=workspace_id, user_id=user.id)
    run = ensure_run_for_workspace(db, run_id=run_id, workspace_id=workspace.id)

    effective_last_id = last_event_id_header or last_event_id

    if effective_last_id:
        logger.info(
            "SSE reconnection: run_id=%s, last_event_id=%s",
            run_id,
            effective_last_id,
        )

    async def _events():
        last_seen: str | None = effective_last_id
        emitted_any = False
        idle_cycles = 0
        max_idle_polls = max(1, settings.signal_stream_max_idle_polls)
        close_idle_polls = max(1, settings.signal_stream_close_idle_polls)
        poll_seconds = max(1, settings.signal_stream_poll_ms) / 1000.0
        max_events_per_batch = 50
        total_events_sent = 0
        max_total_events = 1000

        try:
            yield ": heartbeat\\n\\n"

            while idle_cycles < max_idle_polls and total_events_sent < max_total_events:
                db.expire_all()
                items = list_signals(
                    db,
                    workflow_run_id=run.id,
                    since_id=last_seen,
                    limit=max_events_per_batch,
                )
                fresh = [signal_to_dict(item) for item in items]

                if fresh:
                    emitted_any = True
                    idle_cycles = 0
                    for item in fresh:
                        if total_events_sent >= max_total_events:
                            break
                        event_id = item["id"]
                        payload = {
                            "type": "message",
                            "message": item,
                            "id": event_id,
                        }
                        yield f"id: {event_id}\\n"
                        yield "event: signal\\n"
                        yield f"data: {json.dumps(payload)}\\n\\n"
                        total_events_sent += 1
                else:
                    idle_cycles += 1
                    yield ": ping\\n\\n"

                if items:
                    last_seen = str(items[-1].id)

                if emitted_any and idle_cycles >= close_idle_polls:
                    break

                await asyncio.sleep(poll_seconds)
        except Exception as exc:
            logger.error("SSE stream error: run_id=%s, error=%s", run_id, exc)
            yield "event: error\\n"
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\\n\\n"
        finally:
            yield "event: done\\n"
            yield f"data: {json.dumps({'type': 'done', 'events_sent': total_events_sent})}\\n\\n"

    return StreamingResponse(_events(), media_type="text/event-stream")
