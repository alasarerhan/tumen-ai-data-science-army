"""C4 Agent.

Phase-5 agent wrapper for spec C4.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.c4_rootcause``) with
LangChain ``@tool`` decorators and exposes the standard
``make_c4_rootcause_agent`` factory + ``C4Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``kpi.root_cause``
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

import pandas as pd

from ai_data_science_team.tools.c4_rootcause import (
    DrillDownResult,
    DrillSlice,
    WaterfallResult,
    WaterfallSegment,
    drill_down,
    render_narrative,
    waterfall,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "c4_agent"
NODE_TYPE = "kpi.root_cause"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def c4_waterfall_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``waterfall``.

    Decompose a metric change by a dimension.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c4_waterfall")
    kwargs = {'df': df}
    try:
        result = waterfall(**kwargs)
    except Exception as exc:
        return f"Tool c4_waterfall failed: {exc}", {
            "c4_waterfall": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c4_waterfall: ok"
    return content, {
        "c4_waterfall": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c4_drill_down_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``drill_down``.

    Drill from ``parent_value`` into the next ``child_dimension``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c4_drill_down")
    kwargs = {'df': df}
    try:
        result = drill_down(**kwargs)
    except Exception as exc:
        return f"Tool c4_drill_down failed: {exc}", {
            "c4_drill_down": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c4_drill_down: ok"
    return content, {
        "c4_drill_down": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c4_render_narrative_wrapped(result: WaterfallResult) -> Tuple[str, dict]:
    """Tool wrapper for ``render_narrative``.

    Build a deterministic narrative template.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c4_render_narrative")
    kwargs = {'result': result}
    try:
        result = render_narrative(**kwargs)
    except Exception as exc:
        return f"Tool c4_render_narrative failed: {exc}", {
            "c4_render_narrative": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c4_render_narrative: ok"
    return content, {
        "c4_render_narrative": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


C4_TOOLS = [
    c4_waterfall_wrapped,
    c4_drill_down_wrapped,
    c4_render_narrative_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_c4_rootcause_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the C4 agent."""
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
        tools=C4_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR C4")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the C4 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING C4 RESULTS")
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


class C4Agent(BaseAgent):
    """OO wrapper for the C4 agent (node type ``kpi.root_cause``)."""

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
        return make_c4_rootcause_agent(**self._params)

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
    "C4Agent",
    "make_c4_rootcause_agent",
    "C4_TOOLS",
]
