from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.db.models import AgentExecutionTrace, WorkflowNodeExecution, WorkflowRun

SECRET_KEY_FRAGMENTS = ("password", "secret", "token", "key", "credential", "connection_uri", "uri")
SAFE_TOKEN_USAGE_KEYS = {
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "reasoning_tokens",
}
MAX_ERROR_LENGTH = 800


def start_agent_execution_trace(
    db: Session,
    *,
    run: WorkflowRun,
    node: WorkflowNodeExecution,
) -> AgentExecutionTrace:
    now = datetime.now(UTC)
    trace = AgentExecutionTrace(
        tenant_id=run.tenant_id,
        workspace_id=run.workspace_id,
        workflow_run_id=run.id,
        workflow_node_execution_id=node.id,
        node_id=node.node_id,
        node_type=node.node_type,
        attempt=max(1, int(node.retry_count or 0) + 1),
        executor_kind=node.node_type,
        status="running",
        input_summary_json=json.dumps(_summarize_inputs(_json_loads(node.inputs_json, {}))),
        artifact_ids_json=json.dumps([]),
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(trace)
    db.flush()
    return trace


def complete_agent_execution_trace(
    db: Session,
    *,
    trace: AgentExecutionTrace,
    status: str,
    output: dict[str, Any] | None = None,
    artifact_ids: list[str] | None = None,
    error: str | None = None,
) -> AgentExecutionTrace:
    finished_at = datetime.now(UTC)
    trace.status = status
    trace.output_summary_json = json.dumps(_summarize_outputs(output or {}))
    trace.tool_calls_json = json.dumps(
        _summarize_tool_calls((output or {}).get("outputs", {}).get("tool_calls"))
    )
    trace.artifact_ids_json = json.dumps([str(item) for item in artifact_ids or []])
    trace.token_usage_json = json.dumps(_summarize_named_payload(output or {}, "token_usage"))
    trace.cost_summary_json = json.dumps(_summarize_named_payload(output or {}, "cost_summary"))
    trace.evaluation_summary_json = json.dumps(
        _summarize_named_payload(output or {}, "evaluation_summary")
    )
    trace.version_metadata_json = json.dumps(
        _summarize_named_payload(output or {}, "version_metadata")
    )
    trace.error_summary = _redact_error(error)
    trace.finished_at = finished_at
    trace.duration_ms = max(0, int((finished_at - trace.started_at).total_seconds() * 1000))
    trace.updated_at = finished_at
    db.add(trace)
    db.flush()
    return trace


def list_agent_execution_traces_for_run(
    db: Session,
    *,
    workflow_run_id: uuid.UUID,
) -> list[AgentExecutionTrace]:
    return list(
        db.execute(
            select(AgentExecutionTrace)
            .where(AgentExecutionTrace.workflow_run_id == workflow_run_id)
            .order_by(AgentExecutionTrace.started_at.asc(), AgentExecutionTrace.created_at.asc())
        ).scalars()
    )


def agent_execution_trace_to_dict(trace: AgentExecutionTrace) -> dict[str, Any]:
    return {
        "id": str(trace.id),
        "tenant_id": str(trace.tenant_id),
        "workspace_id": str(trace.workspace_id),
        "workflow_run_id": str(trace.workflow_run_id),
        "workflow_node_execution_id": str(trace.workflow_node_execution_id),
        "node_id": trace.node_id,
        "node_type": trace.node_type,
        "attempt": trace.attempt,
        "executor_kind": trace.executor_kind,
        "status": trace.status,
        "input_summary": _json_loads(trace.input_summary_json, {}),
        "output_summary": _json_loads(trace.output_summary_json, {}),
        "tool_calls": _json_loads(trace.tool_calls_json, []),
        "artifact_ids": _json_loads(trace.artifact_ids_json, []),
        "token_usage": _json_loads(trace.token_usage_json, {}),
        "cost_summary": _json_loads(trace.cost_summary_json, {}),
        "evaluation_summary": _json_loads(trace.evaluation_summary_json, {}),
        "version_metadata": _json_loads(trace.version_metadata_json, {}),
        "error_summary": trace.error_summary,
        "started_at": trace.started_at.isoformat() if trace.started_at else None,
        "finished_at": trace.finished_at.isoformat() if trace.finished_at else None,
        "duration_ms": trace.duration_ms,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
        "updated_at": trace.updated_at.isoformat() if trace.updated_at else None,
    }


def _summarize_inputs(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"payload_type": type(payload).__name__}
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    return {
        "input_keys": _safe_keys(payload),
        "config_keys": _safe_keys(config),
        "has_resources": "resources" in payload,
        "has_retry_policy": "retry_policy" in payload,
        "has_approval_policy": "approval_policy" in payload,
    }


def _summarize_outputs(output: dict[str, Any]) -> dict[str, Any]:
    outputs = output.get("outputs") if isinstance(output.get("outputs"), dict) else {}
    artifacts = output.get("artifacts") if isinstance(output.get("artifacts"), list) else []
    logs = output.get("logs") if isinstance(output.get("logs"), list) else []
    return {
        "status": str(output.get("status") or "succeeded"),
        "output_keys": _safe_keys(outputs),
        "artifact_count": len(artifacts),
        "artifact_types": [
            str(item.get("artifact_type"))
            for item in artifacts
            if isinstance(item, dict) and item.get("artifact_type")
        ],
        "log_count": len(logs),
    }


def _summarize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_tool_calls, list):
        return []
    summaries: list[dict[str, Any]] = []
    for item in raw_tool_calls[:20]:
        if not isinstance(item, dict):
            summaries.append({"type": type(item).__name__})
            continue
        args = item.get("args") if isinstance(item.get("args"), dict) else {}
        summaries.append(
            {
                "name": str(item.get("name") or item.get("tool") or item.get("type") or "tool"),
                "arg_keys": _safe_keys(args),
            }
        )
    return summaries


def _summarize_named_payload(output: dict[str, Any], key: str) -> dict[str, Any]:
    raw = output.get(key)
    outputs = output.get("outputs") if isinstance(output.get("outputs"), dict) else {}
    if raw is None:
        raw = outputs.get(key)
    if not isinstance(raw, dict):
        return {}
    return _redact_payload(raw)


def _redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            string_key = str(key)
            if _looks_sensitive_key(string_key) and string_key.lower() not in SAFE_TOKEN_USAGE_KEYS:
                continue
            safe[string_key] = _redact_payload(value)
        return safe
    if isinstance(payload, list):
        return [_redact_payload(item) for item in payload[:50]]
    if isinstance(payload, (str, int, float, bool)) or payload is None:
        return payload
    return str(type(payload).__name__)


def _safe_keys(payload: dict[str, Any]) -> list[str]:
    return [key for key in sorted(map(str, payload.keys())) if not _looks_sensitive_key(key)]


def _redact_error(error: str | None) -> str | None:
    if not error:
        return None
    sanitized = str(error)
    sanitized = re.sub(r"://[^/@:\s]+:[^/@\s]+@", "://[redacted]@", sanitized)
    for marker in SECRET_KEY_FRAGMENTS:
        sanitized = sanitized.replace(marker, "[redacted-key]")
    return sanitized[:MAX_ERROR_LENGTH]


def _looks_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SECRET_KEY_FRAGMENTS)


def _json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return fallback
