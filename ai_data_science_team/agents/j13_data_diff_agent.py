"""J13 Agent.

Phase-5 agent wrapper for spec J13.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.j13_data_diff``) with
LangChain ``@tool`` decorators and exposes the standard
``make_j13_data_diff_agent`` factory + ``J13Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``data.diff``
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
from typing import List, Dict, Tuple, Set

from ai_data_science_team.tools.j13_data_diff import (
    ColumnStats,
    DiffSummary,
    diff_payload,
    diff_summary,
    key_set_diff,
    numeric_shift,
    profile_columns,
    schema_delta,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "j13_agent"
NODE_TYPE = "data.diff"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def j13_profile_columns_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``profile_columns``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j13_profile_columns")
    kwargs = {'df': df}
    try:
        result = profile_columns(**kwargs)
    except Exception as exc:
        return f"Tool j13_profile_columns failed: {exc}", {
            "j13_profile_columns": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"j13_profile_columns: ok"
    return content, {
        "j13_profile_columns": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j13_numeric_shift_wrapped(left: pd.Series, right: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``numeric_shift``.

    Return mean / std / null_rate shift for a numeric column.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j13_numeric_shift")
    kwargs = {'left': left, 'right': right}
    try:
        result = numeric_shift(**kwargs)
    except Exception as exc:
        return f"Tool j13_numeric_shift failed: {exc}", {
            "j13_numeric_shift": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"j13_numeric_shift: ok"
    return content, {
        "j13_numeric_shift": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j13_schema_delta_wrapped(left: pd.DataFrame, right: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``schema_delta``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j13_schema_delta")
    kwargs = {'left': left, 'right': right}
    try:
        result = schema_delta(**kwargs)
    except Exception as exc:
        return f"Tool j13_schema_delta failed: {exc}", {
            "j13_schema_delta": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"j13_schema_delta: ok"
    return content, {
        "j13_schema_delta": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j13_key_set_diff_wrapped(left: pd.DataFrame, right: pd.DataFrame, key: str) -> Tuple[str, dict]:
    """Tool wrapper for ``key_set_diff``.

    Return (keys_only_in_left, keys_only_in_right).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j13_key_set_diff")
    kwargs = {'left': left, 'right': right, 'key': key}
    try:
        result = key_set_diff(**kwargs)
    except Exception as exc:
        return f"Tool j13_key_set_diff failed: {exc}", {
            "j13_key_set_diff": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"j13_key_set_diff: ok"
    return content, {
        "j13_key_set_diff": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j13_diff_summary_wrapped(left: pd.DataFrame, right: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``diff_summary``.

    Full structural + distribution diff.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j13_diff_summary")
    kwargs = {'left': left, 'right': right}
    try:
        result = diff_summary(**kwargs)
    except Exception as exc:
        return f"Tool j13_diff_summary failed: {exc}", {
            "j13_diff_summary": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"j13_diff_summary: ok"
    return content, {
        "j13_diff_summary": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j13_diff_payload_wrapped(left: pd.DataFrame, right: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``diff_payload``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j13_diff_payload")
    kwargs = {'left': left, 'right': right}
    try:
        result = diff_payload(**kwargs)
    except Exception as exc:
        return f"Tool j13_diff_payload failed: {exc}", {
            "j13_diff_payload": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"j13_diff_payload: ok"
    return content, {
        "j13_diff_payload": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }



J13_TOOLS = [
    j13_profile_columns_wrapped,
    j13_numeric_shift_wrapped,
    j13_schema_delta_wrapped,
    j13_key_set_diff_wrapped,
    j13_diff_summary_wrapped,
    j13_diff_payload_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_j13_data_diff_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J13 agent."""
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
        tools=J13_TOOLS,
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
        logger.info(f"    * RUN REACT AGENT FOR J13")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the J13 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING J13 RESULTS")
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


class J13Agent(BaseAgent):
    """OO wrapper for the J13 agent (node type ``data.diff``)."""

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
        return make_j13_data_diff_agent(**self._params)

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
    "J13Agent",
    "make_j13_data_diff_agent",
    "J13_TOOLS",
]
