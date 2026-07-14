"""J1 Agent.

Phase-5 agent wrapper for spec J1.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.j1_investigation``) with
LangChain ``@tool`` decorators and exposes the standard
``make_j1_investigation_agent`` factory + ``J1Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``kpi.investigate``
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


from ai_data_science_team.tools.j1_investigation import (
    DetectionResult,
    Investigation,
    IsolationResult,
    KPISignal,
    Narrative,
    QuantificationResult,
    detect_change,
    investigate,
    isolate_dimension,
    narrate,
    quantify_contributors,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "j1_agent"
NODE_TYPE = "kpi.investigate"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def j1_detect_change_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``detect_change``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j1_detect_change")
    kwargs = {}
    try:
        result = detect_change(**kwargs)
    except Exception as exc:
        return f"Tool j1_detect_change failed: {exc}", {
            "j1_detect_change": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j1_detect_change: ok"
    return content, {
        "j1_detect_change": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j1_isolate_dimension_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``isolate_dimension``.

    baseline_by_dim: {dimension: {value: kpi_value}}

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j1_isolate_dimension")
    kwargs = {}
    try:
        result = isolate_dimension(**kwargs)
    except Exception as exc:
        return f"Tool j1_isolate_dimension failed: {exc}", {
            "j1_isolate_dimension": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j1_isolate_dimension: ok"
    return content, {
        "j1_isolate_dimension": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j1_quantify_contributors_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``quantify_contributors``.

    contributions: [{'name': 'X', 'baseline': 100, 'current': 80},

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j1_quantify_contributors")
    kwargs = {}
    try:
        result = quantify_contributors(**kwargs)
    except Exception as exc:
        return f"Tool j1_quantify_contributors failed: {exc}", {
            "j1_quantify_contributors": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j1_quantify_contributors: ok"
    return content, {
        "j1_quantify_contributors": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j1_narrate_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``narrate``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j1_narrate")
    kwargs = {}
    try:
        result = narrate(**kwargs)
    except Exception as exc:
        return f"Tool j1_narrate failed: {exc}", {
            "j1_narrate": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j1_narrate: ok"
    return content, {
        "j1_narrate": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j1_investigate_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``investigate``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j1_investigate")
    kwargs = {}
    try:
        result = investigate(**kwargs)
    except Exception as exc:
        return f"Tool j1_investigate failed: {exc}", {
            "j1_investigate": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j1_investigate: ok"
    return content, {
        "j1_investigate": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


J1_TOOLS = [
    j1_detect_change_wrapped,
    j1_isolate_dimension_wrapped,
    j1_quantify_contributors_wrapped,
    j1_narrate_wrapped,
    j1_investigate_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_j1_investigation_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J1 agent."""
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
        tools=J1_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR J1")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the J1 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING J1 RESULTS")
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


class J1Agent(BaseAgent):
    """OO wrapper for the J1 agent (node type ``kpi.investigate``)."""

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
        return make_j1_investigation_agent(**self._params)

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
    "J1Agent",
    "make_j1_investigation_agent",
    "J1_TOOLS",
]
