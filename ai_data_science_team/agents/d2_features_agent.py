"""D2 Agent.

Phase-5 agent wrapper for spec D2.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.d2_features``) with
LangChain ``@tool`` decorators and exposes the standard
``make_d2_features_agent`` factory + ``D2Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``feature.select``
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
from typing import List, Dict

from ai_data_science_team.tools.d2_features import (
    LeakageFinding,
    LeakageReport,
    detect_leakage,
    filter_scores,
    multicollinearity_report,
    select_embedded,
    select_feature,
    select_filter,
    select_wrapper,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "d2_features_agent"
NODE_TYPE = "feature.select"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def d2_filter_scores_wrapped(df: pd.DataFrame, target: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``filter_scores``.

    Compute per-feature filter scores.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_filter_scores")
    kwargs = {'d': df, 'target': target}
    try:
        result = filter_scores(**kwargs)
    except Exception as exc:
        return f"Tool d2_filter_scores failed: {exc}", {
            "d2_filter_scores": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_filter_scores: ok"
    return content, {
        "d2_filter_scores": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d2_select_filter_wrapped(df: pd.DataFrame, target: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``select_filter``.

    Pick the top-``top_k`` features by filter score.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_select_filter")
    kwargs = {'d': df, 'target': target}
    try:
        result = select_filter(**kwargs)
    except Exception as exc:
        return f"Tool d2_select_filter failed: {exc}", {
            "d2_select_filter": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_select_filter: ok"
    return content, {
        "d2_select_filter": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d2_select_wrapper_wrapped(df: pd.DataFrame, target: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``select_wrapper``.

    Greedy forward selection.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_select_wrapper")
    kwargs = {'d': df, 'target': target}
    try:
        result = select_wrapper(**kwargs)
    except Exception as exc:
        return f"Tool d2_select_wrapper failed: {exc}", {
            "d2_select_wrapper": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_select_wrapper: ok"
    return content, {
        "d2_select_wrapper": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d2_select_embedded_wrapped(df: pd.DataFrame, target: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``select_embedded``.

    L1-penalised selection.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_select_embedded")
    kwargs = {'d': df, 'target': target}
    try:
        result = select_embedded(**kwargs)
    except Exception as exc:
        return f"Tool d2_select_embedded failed: {exc}", {
            "d2_select_embedded": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_select_embedded: ok"
    return content, {
        "d2_select_embedded": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d2_detect_leakage_wrapped(df: pd.DataFrame, target: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``detect_leakage``.

    Detect target-leakage suspects.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_detect_leakage")
    kwargs = {'d': df, 'target': target}
    try:
        result = detect_leakage(**kwargs)
    except Exception as exc:
        return f"Tool d2_detect_leakage failed: {exc}", {
            "d2_detect_leakage": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_detect_leakage: ok"
    return content, {
        "d2_detect_leakage": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d2_multicollinearity_report_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``multicollinearity_report``.

    Compute VIF per feature and the Pearson correlation matrix.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_multicollinearity_report")
    kwargs = {'df': df}
    try:
        result = multicollinearity_report(**kwargs)
    except Exception as exc:
        return f"Tool d2_multicollinearity_report failed: {exc}", {
            "d2_multicollinearity_report": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_multicollinearity_report: ok"
    return content, {
        "d2_multicollinearity_report": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d2_select_feature_wrapped(df: pd.DataFrame, target: pd.Series) -> Tuple[str, dict]:
    """Tool wrapper for ``select_feature``.

    Dispatch feature selection by ``method``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d2_select_feature")
    kwargs = {'d': df, 'target': target}
    try:
        result = select_feature(**kwargs)
    except Exception as exc:
        return f"Tool d2_select_feature failed: {exc}", {
            "d2_select_feature": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d2_select_feature: ok"
    return content, {
        "d2_select_feature": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


D2_TOOLS = [
    d2_filter_scores_wrapped,
    d2_select_filter_wrapped,
    d2_select_wrapper_wrapped,
    d2_select_embedded_wrapped,
    d2_detect_leakage_wrapped,
    d2_multicollinearity_report_wrapped,
    d2_select_feature_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_d2_features_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the D2 agent."""
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
        tools=D2_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR D2")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the D2 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING D2 RESULTS")
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


class D2Agent(BaseAgent):
    """OO wrapper for the D2 agent (node type ``feature.select``)."""

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
        return make_d2_features_agent(**self._params)

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
    "D2Agent",
    "make_d2_features_agent",
    "D2_TOOLS",
]
