"""G1 Agent.

Phase-5 agent wrapper for spec G1.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.g1_drift``) with
LangChain ``@tool`` decorators and exposes the standard
``make_g1_drift_agent`` factory + ``G1Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``monitor.drift``
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
import numpy as np
from typing import Dict, Sequence

from ai_data_science_team.tools.g1_drift import (
    G1_DRIFT_TOOL_NAMES,
    drift_signal_payload,
    feature_drift_report,
    ks2,
    performance_drift,
    psi,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "g1_agent"
NODE_TYPE = "monitor.drift"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def g1_psi_wrapped(baseline: Sequence[float] | np.ndarray, current: Sequence[float] | np.ndarray, n_bins: int, eps: float) -> Tuple[str, dict]:
    """Tool wrapper for ``psi``.

    Population Stability Index between two numerical samples.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g1_psi")
    kwargs = {'baseline': baseline, 'current': current, 'n_bins': n_bins, 'eps': eps}
    try:
        result = psi(**kwargs)
    except Exception as exc:
        return f"Tool g1_psi failed: {exc}", {
            "g1_psi": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g1_psi: ok"
    return content, {
        "g1_psi": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g1_ks2_wrapped(baseline: Sequence[float] | np.ndarray, current: Sequence[float] | np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``ks2``.

    Two-sample Kolmogorov–Smirnov statistic (no p-value).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g1_ks2")
    kwargs = {'baseline': baseline, 'current': current}
    try:
        result = ks2(**kwargs)
    except Exception as exc:
        return f"Tool g1_ks2 failed: {exc}", {
            "g1_ks2": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g1_ks2: ok"
    return content, {
        "g1_ks2": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g1_feature_drift_report_wrapped(baseline_df: pd.DataFrame, current_df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``feature_drift_report``.

    Compute per-feature drift between two DataFrames of the same schema.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g1_feature_drift_report")
    kwargs = {'baseline_d': baseline_df, 'current_df': current_df}
    try:
        result = feature_drift_report(**kwargs)
    except Exception as exc:
        return f"Tool g1_feature_drift_report failed: {exc}", {
            "g1_feature_drift_report": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g1_feature_drift_report: ok"
    return content, {
        "g1_feature_drift_report": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g1_performance_drift_wrapped(baseline_metric: float, current_metric: float) -> Tuple[str, dict]:
    """Tool wrapper for ``performance_drift``.

    Compare two scalar metric values and report breach status.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g1_performance_drift")
    kwargs = {'baseline_metric': baseline_metric, 'current_metric': current_metric}
    try:
        result = performance_drift(**kwargs)
    except Exception as exc:
        return f"Tool g1_performance_drift failed: {exc}", {
            "g1_performance_drift": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g1_performance_drift: ok"
    return content, {
        "g1_performance_drift": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g1_drift_signal_payload_wrapped(baseline_df: pd.DataFrame, current_df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``drift_signal_payload``.

    Combine feature-drift and performance-drift into a single payload.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g1_drift_signal_payload")
    kwargs = {'baseline_d': baseline_df, 'current_df': current_df}
    try:
        result = drift_signal_payload(**kwargs)
    except Exception as exc:
        return f"Tool g1_drift_signal_payload failed: {exc}", {
            "g1_drift_signal_payload": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g1_drift_signal_payload: ok"
    return content, {
        "g1_drift_signal_payload": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


G1_TOOLS = [
    g1_psi_wrapped,
    g1_ks2_wrapped,
    g1_feature_drift_report_wrapped,
    g1_performance_drift_wrapped,
    g1_drift_signal_payload_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_g1_drift_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the G1 agent."""
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
        tools=G1_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR G1")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the G1 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING G1 RESULTS")
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


class G1Agent(BaseAgent):
    """OO wrapper for the G1 agent (node type ``monitor.drift``)."""

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
        return make_g1_drift_agent(**self._params)

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
    "G1Agent",
    "make_g1_drift_agent",
    "G1_TOOLS",
]
