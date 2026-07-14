"""G5 Agent.

Phase-5 agent wrapper for spec G5.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.g5_promotion``) with
LangChain ``@tool`` decorators and exposes the standard
``make_g5_promotion_agent`` factory + ``G5Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``deploy.promote``
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from langchain.tools import tool
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Checkpointer
from typing_extensions import Annotated, Sequence, TypedDict

from ai_data_science_team.templates import BaseAgent
from ai_data_science_team.utils.regex import format_agent_name

from typing import List, Dict, Tuple, Optional, Mapping

from ai_data_science_team.tools.g5_promotion import (
    ModelVersionRecord,
    STAGES,
    VALID_TRANSITIONS,
    approve,
    demote,
    evaluate_min_metrics,
    get_version_by_stage,
    mlflow_alias_sync,
    register_version,
    request_promotion,
    validate_signature,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "g5_promotion_agent"
NODE_TYPE = "deploy.promote"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def g5_register_version_wrapped(model_id: str, version: str) -> Tuple[str, dict]:
    """Tool wrapper for ``register_version``.

    Add a new version to the in-memory registry.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_register_version")
    kwargs = {'model_id': model_id, 'version': version}
    try:
        result = register_version(**kwargs)
    except Exception as exc:
        return f"Tool g5_register_version failed: {exc}", {
            "g5_register_version": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_register_version: ok"
    return content, {
        "g5_register_version": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_validate_signature_wrapped(candidate: ModelVersionRecord, target: ModelVersionRecord) -> Tuple[str, dict]:
    """Tool wrapper for ``validate_signature``.

    Check that two records share the same input schema and

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_validate_signature")
    kwargs = {'candidate': candidate, 'target': target}
    try:
        result = validate_signature(**kwargs)
    except Exception as exc:
        return f"Tool g5_validate_signature failed: {exc}", {
            "g5_validate_signature": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_validate_signature: ok"
    return content, {
        "g5_validate_signature": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_evaluate_min_metrics_wrapped(metrics: Mapping[str, float], required: Mapping[str, float]) -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_min_metrics``.

    All required metric thresholds must be met (or exceeded).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_evaluate_min_metrics")
    kwargs = {'metrics': metrics, 'required': required}
    try:
        result = evaluate_min_metrics(**kwargs)
    except Exception as exc:
        return f"Tool g5_evaluate_min_metrics failed: {exc}", {
            "g5_evaluate_min_metrics": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_evaluate_min_metrics: ok"
    return content, {
        "g5_evaluate_min_metrics": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_request_promotion_wrapped(record: ModelVersionRecord, to_stage: str) -> Tuple[str, dict]:
    """Tool wrapper for ``request_promotion``.

    Submit a promotion request.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_request_promotion")
    kwargs = {'record': record, 'to_stage': to_stage}
    try:
        result = request_promotion(**kwargs)
    except Exception as exc:
        return f"Tool g5_request_promotion failed: {exc}", {
            "g5_request_promotion": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_request_promotion: ok"
    return content, {
        "g5_request_promotion": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_approve_wrapped(record: ModelVersionRecord, to_stage: str) -> Tuple[str, dict]:
    """Tool wrapper for ``approve``.

    Approve a pending promotion.  Updates the record's stage

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_approve")
    kwargs = {'record': record, 'to_stage': to_stage}
    try:
        result = approve(**kwargs)
    except Exception as exc:
        return f"Tool g5_approve failed: {exc}", {
            "g5_approve": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_approve: ok"
    return content, {
        "g5_approve": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_demote_wrapped(record: ModelVersionRecord, to_stage: str) -> Tuple[str, dict]:
    """Tool wrapper for ``demote``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_demote")
    kwargs = {'record': record, 'to_stage': to_stage}
    try:
        result = demote(**kwargs)
    except Exception as exc:
        return f"Tool g5_demote failed: {exc}", {
            "g5_demote": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_demote: ok"
    return content, {
        "g5_demote": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_get_version_by_stage_wrapped(registry: Mapping[str, ModelVersionRecord], stage: str) -> Tuple[str, dict]:
    """Tool wrapper for ``get_version_by_stage``.

    Pick the highest version (lexicographic / max) record in

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_get_version_by_stage")
    kwargs = {'registry': registry, 'stage': stage}
    try:
        result = get_version_by_stage(**kwargs)
    except Exception as exc:
        return f"Tool g5_get_version_by_stage failed: {exc}", {
            "g5_get_version_by_stage": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_get_version_by_stage: ok"
    return content, {
        "g5_get_version_by_stage": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g5_mlflow_alias_sync_wrapped(model_id: str, version: str, alias: str, registry_uri: Optional[str]) -> Tuple[str, dict]:
    """Tool wrapper for ``mlflow_alias_sync``.

    Best-effort MLflow alias update.  Returns an in-memory ack

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g5_mlflow_alias_sync")
    kwargs = {'model_id': model_id, 'version': version, 'alias': alias, 'registry_uri': registry_uri}
    try:
        result = mlflow_alias_sync(**kwargs)
    except Exception as exc:
        return f"Tool g5_mlflow_alias_sync failed: {exc}", {
            "g5_mlflow_alias_sync": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g5_mlflow_alias_sync: ok"
    return content, {
        "g5_mlflow_alias_sync": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


G5_TOOLS = [
    g5_register_version_wrapped,
    g5_validate_signature_wrapped,
    g5_evaluate_min_metrics_wrapped,
    g5_request_promotion_wrapped,
    g5_approve_wrapped,
    g5_demote_wrapped,
    g5_get_version_by_stage_wrapped,
    g5_mlflow_alias_sync_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_g5_promotion_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the G5 agent."""
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    from langchain.agents import create_agent

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=G5_TOOLS,
        state_schema=GraphState,
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(AGENT_NAME))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions"))]}

    def run_react_agent(state: GraphState):
        logger.info("    * RUN REACT AGENT FOR G5")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the G5 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING G5 RESULTS")
        internal = state.get("messages", []) or []
        if not internal:
            return {"messages": [], "tool_calls": []}
        last_ai = None
        for msg in reversed(internal):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai = AIMessage(content=getattr(msg, "content", ""), name=AGENT_NAME)
                break
        if last_ai is None:
            last_ai = AIMessage(content=getattr(internal[-1], "content", ""), name=AGENT_NAME)
        tool_calls = []
        for msg in internal:
            name = getattr(getattr(msg, "tool_call_id", None), "name", None) or getattr(msg, "name", None)
            if name:
                tool_calls.append(name)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                logger.info(f"    * Tool: {tc}")
        return {
            "messages": [last_ai],
            "internal_messages": internal,
            "tool_calls": tool_calls,
        }

    workflow = StateGraph(GraphState)
    workflow.add_node("prepare_messages", prepare_messages)
    workflow.add_node("react_agent", react_agent)
    workflow.add_node("post_process", post_process)
    workflow.add_edge(START, "prepare_messages")
    workflow.add_edge("prepare_messages", "react_agent")
    workflow.add_edge("react_agent", "post_process")
    workflow.add_edge("post_process", END)
    return workflow.compile(checkpointer=checkpointer, name=AGENT_NAME)


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class G5Agent(BaseAgent):
    """OO wrapper for the G5 agent (node type ``deploy.promote``)."""

    def __init__(
        self,
        model: Any,
        checkpointer: Optional[Checkpointer] = None,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "checkpointer": checkpointer,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_g5_promotion_agent(**self._params)

    def update_params(self, **kwargs):
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(self, user_instructions: str, **kwargs):
        self.response = self._compiled_graph.invoke(
            {"messages": [("user", user_instructions)]}, **kwargs
        )
        return None

    def get_ai_message(self, markdown: bool = False):
        if not self.response or "messages" not in self.response:
            return None
        from IPython.display import Markdown as _Markdown
        for msg in reversed(self.response.get("messages", [])):
            content = getattr(msg, "content", "")
            if content:
                return _Markdown(content) if markdown else content
        return None

    def get_tool_calls(self):
        if not self.response:
            return None
        return self.response.get("tool_calls")


__all__ = [
    "AGENT_NAME",
    "NODE_TYPE",
    "G5Agent",
    "make_g5_promotion_agent",
    "G5_TOOLS",
]
