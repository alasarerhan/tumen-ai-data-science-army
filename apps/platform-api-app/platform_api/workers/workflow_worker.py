from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from platform_api.core.config import settings
from platform_api.db.models import WorkflowNodeExecution, WorkflowRun
from platform_api.db.session import SessionLocal
from platform_api.services.artifact_service import create_system_artifact_record
from platform_api.services.signal_service import emit_signal
from platform_api.services.workflow_node_executor_service import (
    NodeExecutionContext,
    NodeExecutor,
    get_default_node_executors,
)
from platform_api.services.workflow_queue_service import WORKFLOW_RUN_QUEUE_KEY

logger = logging.getLogger(__name__)

NODE_EXECUTORS: dict[str, NodeExecutor] = {}


def register_node_executor(node_type: str, executor: NodeExecutor) -> None:
    NODE_EXECUTORS[node_type] = executor


class WorkflowWorker:
    def __init__(self, *, consumer_name: str = "workflow-worker", node_executors: dict[str, NodeExecutor] | None = None) -> None:
        self.consumer_name = consumer_name
        default_executors = get_default_node_executors()
        if node_executors is not None:
            default_executors.update(node_executors)
        default_executors.update(NODE_EXECUTORS)
        self.node_executors = default_executors

    def run_once(self) -> dict[str, Any]:
        redis_url = settings.workflow_queue_redis_url.strip() or settings.agent_cache_redis_url.strip()
        if not redis_url:
            return {"processed": False, "reason": "workflow_queue_not_configured"}

        from redis import Redis

        redis = Redis.from_url(redis_url, decode_responses=True)
        messages = redis.xread({WORKFLOW_RUN_QUEUE_KEY: "0-0"}, count=1, block=1)
        if not messages:
            return {"processed": False, "reason": "queue_empty"}

        _stream, items = messages[0]
        message_id, fields = items[0]
        payload = json.loads(fields.get("payload", "{}"))
        run_id = payload.get("run_id")
        result = self.execute_run(run_id)
        redis.xdel(WORKFLOW_RUN_QUEUE_KEY, message_id)
        return {"processed": True, "message_id": message_id, "run_id": run_id, "result": result}

    def execute_run(self, run_id: str) -> dict[str, Any]:
        try:
            parsed_run_id = uuid.UUID(str(run_id))
        except ValueError:
            return {"status": "invalid_run_id"}
        with SessionLocal() as db:
            run = db.execute(select(WorkflowRun).where(WorkflowRun.id == parsed_run_id)).scalar_one_or_none()
            if run is None:
                return {"status": "not_found"}
            nodes = list(
                db.execute(
                    select(WorkflowNodeExecution)
                    .where(WorkflowNodeExecution.workflow_run_id == run.id)
                    .order_by(WorkflowNodeExecution.execution_index.asc(), WorkflowNodeExecution.created_at.asc())
                ).scalars()
            )
            if not nodes:
                return {"status": "processed", "run_status": run.status, "nodes_seen": 0, "nodes_executed": 0}
            executed = 0
            run.status = "RUNNING"
            if run.started_at is None:
                run.started_at = datetime.now(UTC)
            db.add(run)
            for node in nodes:
                if node.status != "queued":
                    continue
                status = self._execute_node(db, run, node)
                executed += 1
                if status in {"failed", "waiting_approval"}:
                    break
            refreshed_nodes = list(
                db.execute(
                    select(WorkflowNodeExecution).where(WorkflowNodeExecution.workflow_run_id == run.id)
                ).scalars()
            )
            terminal_statuses = {node.status for node in refreshed_nodes}
            if refreshed_nodes and terminal_statuses.issubset({"succeeded", "skipped"}):
                run.status = "COMPLETED"
                run.finished_at = datetime.now(UTC)
                run.updated_at = run.finished_at
                db.add(run)
                emit_signal(
                    db,
                    tenant_id=run.tenant_id,
                    workspace_id=run.workspace_id,
                    workflow_run_id=run.id,
                    signal_type="run_completed",
                    target_step=None,
                    note=None,
                    payload={"nodes_executed": executed, "nodes_seen": len(nodes)},
                    created_by_user_id=run.requested_by_user_id,
                )
            db.commit()
            return {"status": "processed", "run_status": run.status, "nodes_seen": len(nodes), "nodes_executed": executed}

    def _execute_node(self, db, run: WorkflowRun, node: WorkflowNodeExecution) -> str:
        now = datetime.now(UTC)
        node.status = "running"
        node.started_at = now
        node.updated_at = now
        db.add(node)
        emit_signal(
            db,
            tenant_id=run.tenant_id,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            signal_type="node_started",
            target_step=node.node_id,
            note=None,
            payload={"node_type": node.node_type},
            created_by_user_id=run.requested_by_user_id,
        )

        executor = self.node_executors.get(node.node_type)
        if executor is None:
            node.status = "failed"
            node.error = f"No executor registered for node type: {node.node_type}"
            node.finished_at = datetime.now(UTC)
            node.updated_at = node.finished_at
            db.add(node)
            emit_signal(
                db,
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                signal_type="node_failed",
                target_step=node.node_id,
                note=node.error,
                payload={"node_type": node.node_type},
                created_by_user_id=run.requested_by_user_id,
            )
            run.status = "FAILED"
            run.finished_at = node.finished_at
            run.updated_at = node.updated_at
            db.add(run)
            return node.status

        try:
            output = executor(NodeExecutionContext(db=db, run=run, node=node))
        except Exception as exc:  # noqa: BLE001 - worker must persist executor failures
            logger.exception("Workflow node execution failed: run_id=%s node_id=%s", run.id, node.node_id)
            node.status = "failed"
            node.error = str(exc)
            node.finished_at = datetime.now(UTC)
            node.updated_at = node.finished_at
            db.add(node)
            run.status = "FAILED"
            run.finished_at = node.finished_at
            run.updated_at = node.updated_at
            db.add(run)
            emit_signal(
                db,
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                signal_type="node_failed",
                target_step=node.node_id,
                note=node.error,
                payload={"node_type": node.node_type},
                created_by_user_id=run.requested_by_user_id,
            )
            return node.status

        produced_artifact_ids = []
        for artifact_payload in output.get("artifacts", []) or []:
            artifact = create_system_artifact_record(
                db,
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                kind=str(artifact_payload["artifact_type"]),
                uri=str(artifact_payload["uri"]),
                produced_by_node_id=node.node_id,
                parent_artifact_ids=[str(item) for item in artifact_payload.get("parent_artifact_ids", [])],
                created_by_user_id=run.requested_by_user_id,
            )
            produced_artifact_ids.append(str(artifact.id))
            emit_signal(
                db,
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                signal_type="artifact_created",
                target_step=node.node_id,
                note=None,
                payload={
                    "node_type": node.node_type,
                    "artifact_id": str(artifact.id),
                    "artifact_type": artifact.kind,
                    "uri": artifact.uri,
                },
                created_by_user_id=run.requested_by_user_id,
            )

        node.status = str(output.get("status") or "succeeded")
        node.outputs_json = json.dumps(output.get("outputs", {}))
        node.logs_json = json.dumps(output.get("logs", []))
        node.produced_artifact_ids_json = json.dumps(produced_artifact_ids)
        node.finished_at = datetime.now(UTC) if node.status != "waiting_approval" else None
        node.updated_at = datetime.now(UTC)
        db.add(node)
        if node.status == "waiting_approval":
            run.status = "WAITING_APPROVAL"
            db.add(run)
            emit_signal(
                db,
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                workflow_run_id=run.id,
                signal_type="approval_required",
                target_step=node.node_id,
                note=None,
                payload={"node_type": node.node_type, "outputs": output.get("outputs", {})},
                created_by_user_id=run.requested_by_user_id,
            )
            return node.status
        emit_signal(
            db,
            tenant_id=run.tenant_id,
            workspace_id=run.workspace_id,
            workflow_run_id=run.id,
            signal_type="node_succeeded",
            target_step=node.node_id,
            note=None,
            payload={"node_type": node.node_type, "produced_artifact_ids": produced_artifact_ids},
            created_by_user_id=run.requested_by_user_id,
        )
        return node.status


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = WorkflowWorker().run_once()
    logger.info("Workflow worker result: %s", result)


if __name__ == "__main__":
    main()
