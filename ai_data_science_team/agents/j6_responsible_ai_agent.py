"""J6 Agent.

Phase-5 agent wrapper for spec J6.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.j6_responsible_ai``) with
LangChain ``@tool`` decorators and exposes the standard
``make_j6_responsible_ai_agent`` factory + ``J6Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.responsible_audit``
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

from typing import List, Dict, Optional, Sequence

from ai_data_science_team.tools.j6_responsible_ai import (
    ErrorSlice,
    ExplainabilityReport,
    FairnessReport,
    FairnessSlice,
    FeatureContribution,
    ResponsibleAIDashboard,
    build_dashboard,
    compute_explainability,
    compute_fairness,
    dashboard_payload,
    discover_error_slices,
    suggest_mitigations,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "j6_responsible_ai_agent"
NODE_TYPE = "model.responsible_audit"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def j6_compute_fairness_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``compute_fairness``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j6_compute_fairness")
    kwargs = {}
    try:
        result = compute_fairness(**kwargs)
    except Exception as exc:
        return f"Tool j6_compute_fairness failed: {exc}", {
            "j6_compute_fairness": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j6_compute_fairness: ok"
    return content, {
        "j6_compute_fairness": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j6_compute_explainability_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``compute_explainability``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j6_compute_explainability")
    kwargs = {}
    try:
        result = compute_explainability(**kwargs)
    except Exception as exc:
        return f"Tool j6_compute_explainability failed: {exc}", {
            "j6_compute_explainability": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j6_compute_explainability: ok"
    return content, {
        "j6_compute_explainability": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j6_discover_error_slices_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``discover_error_slices``.

    Naive slice discovery: walk each feature's value histogram

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j6_discover_error_slices")
    kwargs = {}
    try:
        result = discover_error_slices(**kwargs)
    except Exception as exc:
        return f"Tool j6_discover_error_slices failed: {exc}", {
            "j6_discover_error_slices": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j6_discover_error_slices: ok"
    return content, {
        "j6_discover_error_slices": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j6_suggest_mitigations_wrapped(fairness: Optional[FairnessReport], error_slices: Sequence[ErrorSlice]) -> Tuple[str, dict]:
    """Tool wrapper for ``suggest_mitigations``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j6_suggest_mitigations")
    kwargs = {'fairness': fairness, 'error_slices': error_slices}
    try:
        result = suggest_mitigations(**kwargs)
    except Exception as exc:
        return f"Tool j6_suggest_mitigations failed: {exc}", {
            "j6_suggest_mitigations": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j6_suggest_mitigations: ok"
    return content, {
        "j6_suggest_mitigations": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j6_build_dashboard_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``build_dashboard``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j6_build_dashboard")
    kwargs = {}
    try:
        result = build_dashboard(**kwargs)
    except Exception as exc:
        return f"Tool j6_build_dashboard failed: {exc}", {
            "j6_build_dashboard": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j6_build_dashboard: ok"
    return content, {
        "j6_build_dashboard": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j6_dashboard_payload_wrapped(d: ResponsibleAIDashboard) -> Tuple[str, dict]:
    """Tool wrapper for ``dashboard_payload``.

    Convert dashboard to UI-ready dict (JSON-safe).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j6_dashboard_payload")
    kwargs = {'d': d}
    try:
        result = dashboard_payload(**kwargs)
    except Exception as exc:
        return f"Tool j6_dashboard_payload failed: {exc}", {
            "j6_dashboard_payload": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j6_dashboard_payload: ok"
    return content, {
        "j6_dashboard_payload": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


J6_TOOLS = [
    j6_compute_fairness_wrapped,
    j6_compute_explainability_wrapped,
    j6_discover_error_slices_wrapped,
    j6_suggest_mitigations_wrapped,
    j6_build_dashboard_wrapped,
    j6_dashboard_payload_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_j6_responsible_ai_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J6 agent."""
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
        tools=J6_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR J6")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the J6 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING J6 RESULTS")
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


class J6Agent(BaseAgent):
    """OO wrapper for the J6 agent (node type ``model.responsible_audit``)."""

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
        return make_j6_responsible_ai_agent(**self._params)

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
    "J6Agent",
    "make_j6_responsible_ai_agent",
    "J6_TOOLS",
]
