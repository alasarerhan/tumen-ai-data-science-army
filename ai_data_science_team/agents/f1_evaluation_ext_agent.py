"""F1 Agent.

Phase-5 agent wrapper for spec F1.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.f1_evaluation_ext``) with
LangChain ``@tool`` decorators and exposes the standard
``make_f1_evaluation_ext_agent`` factory + ``F1Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.evaluate.ext``
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
from typing import List, Dict, Sequence

from ai_data_science_team.tools.f1_evaluation_ext import (
    CalibrationReport,
    F1_EVALUATION_EXT_TOOL_NAMES,
    SegmentRow,
    ThresholdReport,
    evaluate_calibration,
    evaluate_segments,
    optimize_threshold,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "f1_agent"
NODE_TYPE = "model.evaluate.ext"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def f1_evaluate_calibration_wrapped(y_true: Sequence[int], y_prob: Sequence[float], n_bins: int) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": CalibrationReport,
    "content": str,
}]:
    """Tool wrapper for ``evaluate_calibration``.

    Compute calibration metrics for a binary classifier.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f1_evaluate_calibration")
    kwargs = {'y_true': y_true, 'y_prob': y_prob, 'n_bins': n_bins}
    try:
        result = evaluate_calibration(**kwargs)
    except Exception as exc:
        return f"Tool f1_evaluate_calibration failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"f1_evaluate_calibration: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f1_optimize_threshold_wrapped(y_true: Sequence[int], y_prob: Sequence[float]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": ThresholdReport,
    "content": str,
}]:
    """Tool wrapper for ``optimize_threshold``.

    Sweep thresholds from 0 to 1 by ``step`` and pick the argmin.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f1_optimize_threshold")
    kwargs = {'y_true': y_true, 'y_prob': y_prob}
    try:
        result = optimize_threshold(**kwargs)
    except Exception as exc:
        return f"Tool f1_optimize_threshold failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"f1_optimize_threshold: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f1_evaluate_segments_wrapped(df: pd.DataFrame, y_true: Sequence[int], y_pred: Sequence[int], segment_columns: Sequence[str]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": List[Dict[str, Any]],
    "content": str,
}]:
    """Tool wrapper for ``evaluate_segments``.

    Per-segment metrics table.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f1_evaluate_segments")
    kwargs = {'df': df, 'y_true': y_true, 'y_pred': y_pred, 'segment_columns': segment_columns}
    try:
        result = evaluate_segments(**kwargs)
    except Exception as exc:
        return f"Tool f1_evaluate_segments failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"f1_evaluate_segments: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }



F1_TOOLS = [
    f1_evaluate_calibration_wrapped,
    f1_optimize_threshold_wrapped,
    f1_evaluate_segments_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_f1_evaluation_ext_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the F1 agent."""
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
        tools=F1_TOOLS,
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
        logger.info(f"    * RUN REACT AGENT FOR {spec_id}")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the F1 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING F1 RESULTS")
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


class F1Agent(BaseAgent):
    """OO wrapper for the F1 agent (node type ``model.evaluate.ext``)."""

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
        return make_f1_evaluation_ext_agent(**self._params)

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
    "F1Agent",
    "make_f1_evaluation_ext_agent",
    "F1_TOOLS",
]
