"""Human-in-the-Loop (HITL) Tools — M17.

Pure‐Python LangChain tools for managing approval workflows inside an
``ApprovalGateAgent``.  All tools use the
``@tool(response_format="content_and_artifact")`` convention so they return a
``Tuple[str, Dict]`` where the second element is also stored in the agent's
artifact memory.

Tools
-----
``create_approval_request``
    Builds a structured approval‐request record with a unique id.
``format_approval_notification``
    Converts an approval‐request dict into a human‐readable notification
    (Markdown string).
``check_approval_status``
    Looks up the current status of a request by id from an in‐memory store.
``log_approval_decision``
    Records a human decision against a request id and stores the audit entry.
``summarize_for_approval``
    Produces a concise bullet‐point summary of an agent output dict for easy
    human review.

Usage::

    from ai_data_science_team.tools.hitl import (
        create_approval_request,
        format_approval_notification,
        check_approval_status,
        log_approval_decision,
        summarize_for_approval,
    )

    content, artifact = create_approval_request.func(
        step_name="feature_engineering",
        description="One‐hot encode and scale all numeric columns",
        data_summary="10 000 rows × 25 columns",
        risk_level="medium",
        agent_name="FeatureEngineeringAgent",
    )
    logger.info(content)
    logger.info(artifact)
"""
from __future__ import annotations



import logging

logger = logging.getLogger(__name__)
import datetime
import json
import threading
import uuid
from typing import Dict, Optional, Tuple

from langchain.tools import tool

_APPROVAL_STORE: Dict[str, Dict] = {}
_DECISION_LOG: list = []
_hitl_lock = threading.Lock()


def _reset_stores() -> None:
    """Reset in‐memory stores (used by tests)."""
    with _hitl_lock:
        _APPROVAL_STORE.clear()
        _DECISION_LOG.clear()


# ---------------------------------------------------------------------------
# 1. create_approval_request
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def create_approval_request(
    step_name: str,
    description: str,
    data_summary: str = "",
    risk_level: str = "medium",
    agent_name: str = "UnknownAgent",
) -> Tuple[str, Dict]:
    """Create a structured approval‐request record with a unique UUID.

    Parameters
    ----------
    step_name : str
        Short label for the pipeline step requiring approval,
        e.g. ``"feature_engineering"``.
    description : str
        Human‐readable description of what the step will do.
    data_summary : str, optional
        Brief summary of the data involved (row/column counts, key stats).
    risk_level : str, optional
        Perceived risk: ``"low"``, ``"medium"``, or ``"high"``. Default ``"medium"``.
    agent_name : str, optional
        Name of the agent requesting approval.

    Returns
    -------
    Tuple[str, Dict]
        ``(content_message, artifact_dict)``
    """
    valid_risk = {"low", "medium", "high"}
    risk_level = risk_level.lower() if risk_level.lower() in valid_risk else "medium"

    request_id = str(uuid.uuid4())
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    record: Dict = {
        "request_id": request_id,
        "step_name": step_name,
        "agent_name": agent_name,
        "description": description,
        "data_summary": data_summary,
        "risk_level": risk_level,
        "status": "pending",
        "created_at": timestamp,
        "decision": None,
        "decision_reason": None,
        "decided_by": None,
        "decided_at": None,
    }

    with _hitl_lock:
        _APPROVAL_STORE[request_id] = record

    content = (
        f"Approval request created. ID: {request_id} | Step: {step_name}"
        f" | Risk: {risk_level} | Status: pending"
    )
    return content, record


# ---------------------------------------------------------------------------
# 2. format_approval_notification
# ---------------------------------------------------------------------------
# 2. format_approval_notification
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def format_approval_notification(
    request_json: str,
    channel: str = "ui",
    urgency: str = "normal",
) -> Tuple[str, Dict]:
    """Format an approval‐request dict into a human‐readable Markdown notification.

    Parameters
    ----------
    request_json : str
        JSON string of an approval‐request dict (as returned by
        ``create_approval_request``).
    channel : str, optional
        Delivery channel hint: ``"ui"``, ``"email"``, or ``"slack"``.
        Default ``"ui"``.
    urgency : str, optional
        Urgency level: ``"low"``, ``"normal"``, or ``"high"``. Default ``"normal"``.

    Returns
    -------
    Tuple[str, Dict]
        ``(notification_markdown, artifact_dict)``
    """
    try:
        request: Dict = json.loads(request_json)
    except (json.JSONDecodeError, TypeError):
        artifact = {"error": "invalid_json", "raw": str(request_json)}
        return "ERROR: request_json is not valid JSON.", artifact

    urgency_icon = {"low": "🟢", "normal": "🟡", "high": "🔴"}.get(
        urgency.lower(), "🟡"
    )
    risk_icon = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(
        request.get("risk_level", "medium"), "🟡"
    )

    markdown = (
        f"## {urgency_icon} Approval Required — {request.get('step_name', 'Unknown Step')}\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Request ID** | `{request.get('request_id', 'N/A')}` |\n"
        f"| **Agent** | {request.get('agent_name', 'N/A')} |\n"
        f"| **Channel** | {channel} |\n"
        f"| **Urgency** | {urgency} |\n"
        f"| **Risk Level** | {risk_icon} {request.get('risk_level', 'N/A')} |\n"
        f"| **Status** | {request.get('status', 'N/A')} |\n"
        f"| **Created At** | {request.get('created_at', 'N/A')} |\n\n"
        f"### Description\n{request.get('description', '')}\n\n"
    )

    if request.get("data_summary"):
        markdown += f"### Data Summary\n{request['data_summary']}\n\n"

    markdown += (
        "### Action Required\n"
        "Reply **`yes`** to approve, or provide modification instructions.\n"
    )

    artifact: Dict = {
        "notification_markdown": markdown,
        "request_id": request.get("request_id"),
        "channel": channel,
        "urgency": urgency,
        "risk_level": request.get("risk_level"),
        "step_name": request.get("step_name"),
    }

    return markdown, artifact


# ---------------------------------------------------------------------------
# 3. check_approval_status
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def check_approval_status(
    request_id: str,
) -> Tuple[str, Dict]:
    """Look up the current status of an approval request by its ID.

    Parameters
    ----------
    request_id : str
        The UUID‐prefix id returned by ``create_approval_request``.

    Returns
    -------
    Tuple[str, Dict]
        ``(status_summary_string, status_artifact)``
    """
    with _hitl_lock:
        record = _APPROVAL_STORE.get(request_id)

        if record is None:
            artifact = {
                "request_id": request_id,
                "status": "not_found",
                "error": f"No approval request found with id '{request_id}'",
            }
            return f"Approval request '{request_id}' not found.", artifact

        status = record.get("status", "unknown")
        content = (
            f"Request '{request_id}' | Step: {record.get('step_name')}"
            f" | Status: {status}"
            + (f" | Decision: {record.get('decision')}" if record.get("decision") else "")
        )

        artifact: Dict = {
            "request_id": request_id,
            "status": status,
            "step_name": record.get("step_name"),
            "decision": record.get("decision"),
            "decision_reason": record.get("decision_reason"),
            "decided_by": record.get("decided_by"),
            "decided_at": record.get("decided_at"),
        }

    return content, artifact


# ---------------------------------------------------------------------------
# 4. log_approval_decision
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def log_approval_decision(
    request_id: str,
    decision: str,
    reason: str = "",
    modifier: str = "human",
) -> Tuple[str, Dict]:
    """Record a human decision for an approval request and update its status.

    Parameters
    ----------
    request_id : str
        The id of the approval request being decided upon.
    decision : str
        Decision value: ``"approved"``, ``"rejected"``, or ``"modified"``.
    reason : str, optional
        Free‐text explanation of the decision.
    modifier : str, optional
        Who made the decision (e.g. ``"human"``, ``"supervisor_agent"``).

    Returns
    -------
    Tuple[str, Dict]
        ``(audit_message, audit_log_entry)``
    """
    valid_decisions = {"approved", "rejected", "modified"}
    decision_norm = decision.lower() if decision.lower() in valid_decisions else "modified"

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    log_entry: Dict = {
        "request_id": request_id,
        "decision": decision_norm,
        "reason": reason,
        "modifier": modifier,
        "decided_at": timestamp,
    }

    with _hitl_lock:
        if request_id in _APPROVAL_STORE:
            _APPROVAL_STORE[request_id]["status"] = (
                "approved" if decision_norm == "approved" else
                "rejected" if decision_norm == "rejected" else
                "modified"
            )
            _APPROVAL_STORE[request_id]["decision"] = decision_norm
            _APPROVAL_STORE[request_id]["decision_reason"] = reason
            _APPROVAL_STORE[request_id]["decided_by"] = modifier
            _APPROVAL_STORE[request_id]["decided_at"] = timestamp

        _DECISION_LOG.append(log_entry)

    content = (
        f"Decision logged: request '{request_id}' → {decision_norm}"
        + (f" (by {modifier})" if modifier else "")
    )
    return content, log_entry


# ---------------------------------------------------------------------------
# 5. summarize_for_approval
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def summarize_for_approval(
    agent_output_json: str,
    max_length: int = 500,
    focus_keys: Optional[str] = None,
) -> Tuple[str, Dict]:
    """Produce a concise bullet‐point summary of an agent output for human review.

    Parameters
    ----------
    agent_output_json : str
        JSON string of the agent's output artifact dict.
    max_length : int, optional
        Approximate maximum character length for the summary body. Default 500.
    focus_keys : str, optional
        Comma‐separated list of keys to emphasise in the summary.

    Returns
    -------
    Tuple[str, Dict]
        ``(summary_markdown, artifact_dict)``
    """
    try:
        output: Dict = json.loads(agent_output_json)
    except (json.JSONDecodeError, TypeError):
        artifact = {"error": "invalid_json", "raw": str(agent_output_json)}
        return "ERROR: agent_output_json is not valid JSON.", artifact

    focus_list = (
        [k.strip() for k in focus_keys.split(",") if k.strip()]
        if focus_keys
        else []
    )

    lines = []
    char_count = 0

    # Prioritise focus keys first
    ordered_keys = (
        [k for k in focus_list if k in output]
        + [k for k in output if k not in focus_list]
    )

    for key in ordered_keys:
        val = output[key]
        val_str = (
            json.dumps(val, default=str)
            if isinstance(val, (dict, list))
            else str(val)
        )
        if len(val_str) > 120:
            val_str = val_str[:117] + "..."
        line = f"- **{key}**: {val_str}"
        char_count += len(line)
        if char_count > max_length and lines:
            lines.append(f"- *(and {len(output) - len(lines)} more fields …)*")
            break
        lines.append(line)

    summary_body = "\n".join(lines) if lines else "*(no data)*"
    summary_md = f"### Agent Output Summary\n\n{summary_body}\n"

    artifact: Dict = {
        "summary_markdown": summary_md,
        "total_keys": len(output),
        "summarised_keys": min(len(lines), len(output)),
        "focus_keys": focus_list,
        "max_length": max_length,
    }

    return summary_md, artifact
