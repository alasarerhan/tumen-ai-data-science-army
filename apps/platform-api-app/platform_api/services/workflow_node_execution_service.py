from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.core.service_errors import ConflictError, NotFoundError
from platform_api.db.models import WorkflowNodeExecution, WorkflowRun
from platform_api.services.workflow_ir_service import adapt_workflow_spec_to_v2

TERMINAL_NODE_STATUSES = {"succeeded", "failed", "skipped"}
RETRYABLE_NODE_STATUSES = {"failed", "retrying"}


def node_execution_to_dict(node: WorkflowNodeExecution) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "tenant_id": str(node.tenant_id),
        "workspace_id": str(node.workspace_id),
        "workflow_run_id": str(node.workflow_run_id),
        "node_id": node.node_id,
        "node_type": node.node_type,
        "execution_index": node.execution_index,
        "status": node.status,
        "inputs": json.loads(node.inputs_json) if node.inputs_json else {},
        "outputs": json.loads(node.outputs_json) if node.outputs_json else {},
        "logs": json.loads(node.logs_json) if node.logs_json else [],
        "error": node.error,
        "retry_count": node.retry_count,
        "produced_artifact_ids": json.loads(node.produced_artifact_ids_json) if node.produced_artifact_ids_json else [],
        "started_at": node.started_at.isoformat() if node.started_at else None,
        "finished_at": node.finished_at.isoformat() if node.finished_at else None,
        "created_at": node.created_at.isoformat() if node.created_at else None,
        "updated_at": node.updated_at.isoformat() if node.updated_at else None,
    }


def create_node_executions_for_run(
    db: Session,
    *,
    run: WorkflowRun,
    workflow_spec: dict[str, Any] | None,
) -> list[WorkflowNodeExecution]:
    if not workflow_spec:
        return []
    document = adapt_workflow_spec_to_v2(workflow_spec)
    records: list[WorkflowNodeExecution] = []
    for index, node in enumerate(document.get("nodes", [])):
        node_id = str(node.get("id", ""))
        node_type = str(node.get("type") or node.get("data", {}).get("type") or node.get("data", {}).get("agent") or "")
        if not node_id or not node_type:
            continue
        inputs_payload = _build_node_inputs_payload(node)
        record = WorkflowNodeExecution(
            tenant_id=run.tenant_id,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            node_id=node_id,
            node_type=node_type,
            execution_index=index,
            status="queued",
            inputs_json=json.dumps(inputs_payload),
            outputs_json=json.dumps(node.get("outputs", {})),
            logs_json=json.dumps([]),
            retry_count=0,
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records


def _build_node_inputs_payload(node: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    raw_inputs = node.get("inputs", {})
    if isinstance(raw_inputs, dict):
        payload.update(raw_inputs)
    elif raw_inputs:
        payload["inputs"] = raw_inputs
    for key in (
        "config",
        "resources",
        "timeout_seconds",
        "retry_policy",
        "fallback_policy",
        "approval_policy",
    ):
        if key in node:
            payload[key] = node[key]
    return payload


def list_node_executions_for_run(
    db: Session,
    *,
    workflow_run_id: uuid.UUID,
) -> list[WorkflowNodeExecution]:
    return list(
        db.execute(
            select(WorkflowNodeExecution)
            .where(WorkflowNodeExecution.workflow_run_id == workflow_run_id)
            .order_by(WorkflowNodeExecution.execution_index.asc(), WorkflowNodeExecution.created_at.asc())
        ).scalars()
    )


def get_node_execution_for_update(
    db: Session,
    *,
    workflow_run_id: uuid.UUID,
    node_id: str,
) -> WorkflowNodeExecution:
    record = db.execute(
        select(WorkflowNodeExecution)
        .where(
            WorkflowNodeExecution.workflow_run_id == workflow_run_id,
            WorkflowNodeExecution.node_id == node_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if record is None:
        raise NotFoundError("Workflow node execution not found")
    return record


def retry_node_execution(
    db: Session,
    *,
    run: WorkflowRun,
    node_id: str,
) -> WorkflowNodeExecution:
    record = get_node_execution_for_update(db, workflow_run_id=run.id, node_id=node_id)
    if record.status not in RETRYABLE_NODE_STATUSES:
        raise ConflictError(f"Node is not retryable from status: {record.status}")
    record.status = "queued"
    record.retry_count += 1
    record.error = None
    record.finished_at = None
    record.updated_at = datetime.now(UTC)
    run.status = "SCHEDULED"
    db.add(record)
    db.add(run)
    db.flush()
    return record


def resume_run_from_failed_node(db: Session, *, run: WorkflowRun) -> list[WorkflowNodeExecution]:
    records = list_node_executions_for_run(db, workflow_run_id=run.id)
    resumable = [record for record in records if record.status in {"failed", "retrying"}]
    if not resumable:
        raise ConflictError("Run has no failed or retrying nodes to resume")
    for record in resumable:
        record.status = "queued"
        record.error = None
        record.finished_at = None
        record.updated_at = datetime.now(UTC)
        db.add(record)
    run.status = "SCHEDULED"
    db.add(run)
    db.flush()
    return resumable
