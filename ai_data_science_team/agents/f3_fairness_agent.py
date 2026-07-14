"""F3 Agent.

Phase-5 agent wrapper for spec F3.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.f3_fairness``) with
LangChain ``@tool`` decorators and exposes the standard
``make_f3_fairness_agent`` factory + ``F3Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.fairness_audit``
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
from typing import Dict, Optional, Sequence

from ai_data_science_team.tools.f3_fairness import (
    F3_FAIRNESS_TOOL_NAMES,
    FOUR_FIFTHS,
    FairnessReport,
    audit_fairness,
    demographic_parity_difference,
    demographic_parity_ratio,
    equalized_odds_difference,
    per_group_metrics,
    simulate_threshold_mitigation,
    violates_four_fifths,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "f3_agent"
NODE_TYPE = "model.fairness_audit"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def f3_per_group_metrics_wrapped(y_true: Sequence[int], y_pred: Sequence[int], sensitive: Sequence) -> Tuple[str, dict]:
    """Tool wrapper for ``per_group_metrics``.

    Per-group base rates + selection/TPR/FPR.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_per_group_metrics")
    kwargs = {'y_true': y_true, 'y_pred': y_pred, 'sensitive': sensitive}
    try:
        result = per_group_metrics(**kwargs)
    except Exception as exc:
        return f"Tool f3_per_group_metrics failed: {exc}", {
            "f3_per_group_metrics": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_per_group_metrics: ok"
    return content, {
        "f3_per_group_metrics": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f3_demographic_parity_difference_wrapped(group_df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``demographic_parity_difference``.

    Max selection_rate − min selection_rate across groups.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_demographic_parity_difference")
    kwargs = {'group_df': group_df}
    try:
        result = demographic_parity_difference(**kwargs)
    except Exception as exc:
        return f"Tool f3_demographic_parity_difference failed: {exc}", {
            "f3_demographic_parity_difference": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_demographic_parity_difference: ok"
    return content, {
        "f3_demographic_parity_difference": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f3_demographic_parity_ratio_wrapped(group_df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``demographic_parity_ratio``.

    Min / max selection_rate.  Range 0-1, 1 = perfect parity.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_demographic_parity_ratio")
    kwargs = {'group_df': group_df}
    try:
        result = demographic_parity_ratio(**kwargs)
    except Exception as exc:
        return f"Tool f3_demographic_parity_ratio failed: {exc}", {
            "f3_demographic_parity_ratio": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_demographic_parity_ratio: ok"
    return content, {
        "f3_demographic_parity_ratio": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f3_equalized_odds_difference_wrapped(group_df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``equalized_odds_difference``.

    Max TPR − min TPR (FPR contribution is symmetrical; we

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_equalized_odds_difference")
    kwargs = {'group_df': group_df}
    try:
        result = equalized_odds_difference(**kwargs)
    except Exception as exc:
        return f"Tool f3_equalized_odds_difference failed: {exc}", {
            "f3_equalized_odds_difference": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_equalized_odds_difference: ok"
    return content, {
        "f3_equalized_odds_difference": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f3_violates_four_fifths_wrapped(group_df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``violates_four_fifths``.

    Return per-group violation of the 80% rule (ratio < threshold).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_violates_four_fifths")
    kwargs = {'group_df': group_df}
    try:
        result = violates_four_fifths(**kwargs)
    except Exception as exc:
        return f"Tool f3_violates_four_fifths failed: {exc}", {
            "f3_violates_four_fifths": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_violates_four_fifths: ok"
    return content, {
        "f3_violates_four_fifths": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f3_simulate_threshold_mitigation_wrapped(y_true: Sequence[int], y_pred_proba: Sequence[float], sensitive: Sequence, target_rate: Optional[float]) -> Tuple[str, dict]:
    """Tool wrapper for ``simulate_threshold_mitigation``.

    Simulate equalized-odds post-processing by picking per-group

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_simulate_threshold_mitigation")
    kwargs = {'y_true': y_true, 'y_pred_proba': y_pred_proba, 'sensitive': sensitive, 'target_rate': target_rate}
    try:
        result = simulate_threshold_mitigation(**kwargs)
    except Exception as exc:
        return f"Tool f3_simulate_threshold_mitigation failed: {exc}", {
            "f3_simulate_threshold_mitigation": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_simulate_threshold_mitigation: ok"
    return content, {
        "f3_simulate_threshold_mitigation": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f3_audit_fairness_wrapped(y_true: Sequence[int], y_pred: Sequence[int], sensitive: Sequence) -> Tuple[str, dict]:
    """Tool wrapper for ``audit_fairness``.

    Run the full F3 audit on a single protected attribute.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f3_audit_fairness")
    kwargs = {'y_true': y_true, 'y_pred': y_pred, 'sensitive': sensitive}
    try:
        result = audit_fairness(**kwargs)
    except Exception as exc:
        return f"Tool f3_audit_fairness failed: {exc}", {
            "f3_audit_fairness": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "f3_audit_fairness: ok"
    return content, {
        "f3_audit_fairness": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


F3_TOOLS = [
    f3_per_group_metrics_wrapped,
    f3_demographic_parity_difference_wrapped,
    f3_demographic_parity_ratio_wrapped,
    f3_equalized_odds_difference_wrapped,
    f3_violates_four_fifths_wrapped,
    f3_simulate_threshold_mitigation_wrapped,
    f3_audit_fairness_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_f3_fairness_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the F3 agent."""
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
        tools=F3_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR F3")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the F3 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING F3 RESULTS")
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


class F3Agent(BaseAgent):
    """OO wrapper for the F3 agent (node type ``model.fairness_audit``)."""

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
        return make_f3_fairness_agent(**self._params)

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
    "F3Agent",
    "make_f3_fairness_agent",
    "F3_TOOLS",
]
