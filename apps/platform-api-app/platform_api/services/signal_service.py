from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from ai_data_science_team.signals import SignalType, WorkflowSignal
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import WorkflowRun, WorkflowSignalEvent
from platform_api.orchestration.runtime_state import get_orchestration_signal_store
from platform_api.core.service_errors import NotFoundError, UnprocessableEntityError, ValidationError

logger = logging.getLogger(__name__)


ALLOWED_SIGNAL_TYPES = {
    "pause",
    "resume",
    "skip",
    "modify",
    "annotate",
    "cancel",
    "node_started",
    "node_progress",
    "node_succeeded",
    "node_failed",
    "artifact_created",
    "approval_required",
    "run_completed",
}


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid {label}") from exc


def ensure_run_for_workspace(
    db: Session,
    *,
    run_id: str,
    workspace_id: uuid.UUID,
) -> WorkflowRun:
    """Ensure a workflow run exists and belongs to the specified workspace.

    Security: workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities.
    """
    rid = _parse_uuid(run_id, "run_id")
    run = db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == rid,
            WorkflowRun.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError("Workflow run not found")
    return run


def emit_signal(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    workflow_run_id: uuid.UUID,
    signal_type: str,
    target_step: str | None,
    note: str | None,
    payload: dict | None,
    created_by_user_id: uuid.UUID | None,
) -> WorkflowSignalEvent:
    if signal_type not in ALLOWED_SIGNAL_TYPES:
        allowed = ", ".join(sorted(ALLOWED_SIGNAL_TYPES))
        raise UnprocessableEntityError(
            f"Unsupported signal_type. Allowed values: {allowed}"
        )

    event = WorkflowSignalEvent(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        workflow_run_id=workflow_run_id,
        signal_type=signal_type,
        target_step=target_step,
        note=note,
        payload_json=json.dumps(payload or {}),
        created_by_user_id=created_by_user_id,
        created_at=datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    _mirror_signal_to_staged_runtime(
        run=_load_run_for_signal_bridge(db, workflow_run_id=workflow_run_id),
        signal_type=signal_type,
        target_step=target_step,
        note=note,
        payload=payload or {},
    )
    return event


def _load_run_for_signal_bridge(db: Session, workflow_run_id: uuid.UUID) -> WorkflowRun:
    run = db.get(WorkflowRun, workflow_run_id)
    if run is None:
        raise NotFoundError("Workflow run not found")
    return run


def _mirror_signal_to_staged_runtime(
    *,
    run: WorkflowRun,
    signal_type: str,
    target_step: str | None,
    note: str | None,
    payload: dict,
) -> None:
    if settings.orchestration_execution_mode.strip().lower() != "staged_m22":
        return

    session_id = (run.prefect_flow_run_id or "").strip()
    if not session_id:
        logger.warning(
            "Skipping staged M22 signal mirror because workflow run %s has no prefect_flow_run_id",
            run.id,
        )
        return

    try:
        merged_payload = dict(payload)
        if note and "note" not in merged_payload:
            merged_payload["note"] = note
        get_orchestration_signal_store().emit(
            WorkflowSignal(
                type=SignalType(signal_type),
                session_id=session_id,
                step_id=target_step,
                payload=merged_payload,
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to mirror workflow signal %s for staged M22 session %s: %s",
            signal_type,
            session_id,
            exc,
        )


def list_signals(
    db: Session,
    *,
    workflow_run_id: uuid.UUID,
    since_id: str | None = None,
    limit: int | None = None,
) -> list[WorkflowSignalEvent]:
    query = select(WorkflowSignalEvent).where(WorkflowSignalEvent.workflow_run_id == workflow_run_id)
    cursor_uuid: uuid.UUID | None = None
    if since_id:
        cursor_uuid = _parse_uuid(since_id, "since_id")
    query = query.order_by(WorkflowSignalEvent.created_at.asc(), WorkflowSignalEvent.id.asc())
    if limit is not None and cursor_uuid is None:
        query = query.limit(limit)
    rows = list(db.execute(query).scalars())
    if cursor_uuid is not None:
        for index, row in enumerate(rows):
            if row.id == cursor_uuid:
                rows = rows[index + 1 :]
                break
    if limit is not None:
        rows = rows[:limit]
    return rows


def signal_to_dict(event: WorkflowSignalEvent) -> dict:
    payload: dict = {}
    if event.payload_json:
        try:
            payload = json.loads(event.payload_json)
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse payload JSON for signal %s: %s",
                event.id, e,
            )
            payload = {}
    return {
        "id": str(event.id),
        "workflow_run_id": str(event.workflow_run_id),
        "signal_type": event.signal_type,
        "target_step": event.target_step,
        "note": event.note,
        "payload": payload,
        "created_by_user_id": str(event.created_by_user_id) if event.created_by_user_id else None,
        "created_at": event.created_at.isoformat() if event.created_at else datetime.now(UTC).isoformat(),
    }


