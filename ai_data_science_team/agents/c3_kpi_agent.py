"""C3 Agent.

Phase-5 agent wrapper for spec C3.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.c3_kpi``) with
LangChain ``@tool`` decorators and exposes the standard
``make_c3_kpi_agent`` factory + ``C3Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``kpi.compute``
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
from typing import List, Dict, Optional, Sequence, Mapping

from ai_data_science_team.tools.c3_kpi import (
    ALARM_KINDS,
    AlarmRule,
    KPIHistory,
    PERIODS,
    build_alarm,
    check_alarm,
    compute_schedule,
    define_kpi,
    evaluate_and_record,
    evaluate_python_code,
    make_history,
    record_period,
    sparkline_points,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "c3_kpi_agent"
NODE_TYPE = "kpi.compute"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def c3_define_kpi_wrapped(name: str, code: str) -> Tuple[str, dict]:
    """Tool wrapper for ``define_kpi``.

    Build a KPI definition dict.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_define_kpi")
    kwargs = {'name': name, 'code': code}
    try:
        result = define_kpi(**kwargs)
    except Exception as exc:
        return f"Tool c3_define_kpi failed: {exc}", {
            "c3_define_kpi": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_define_kpi: ok"
    return content, {
        "c3_define_kpi": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_evaluate_python_code_wrapped(kpi: Mapping[str, Any], dataframe: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_python_code``.

    Run the KPI's Python expression against ``dataframe``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_evaluate_python_code")
    kwargs = {'kpi': kpi, 'dataframe': dataframe}
    try:
        result = evaluate_python_code(**kwargs)
    except Exception as exc:
        return f"Tool c3_evaluate_python_code failed: {exc}", {
            "c3_evaluate_python_code": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_evaluate_python_code: ok"
    return content, {
        "c3_evaluate_python_code": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_compute_schedule_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``compute_schedule``.

    Generate the timestamps for the last ``lookback_steps`` periods.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_compute_schedule")
    kwargs = {}
    try:
        result = compute_schedule(**kwargs)
    except Exception as exc:
        return f"Tool c3_compute_schedule failed: {exc}", {
            "c3_compute_schedule": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_compute_schedule: ok"
    return content, {
        "c3_compute_schedule": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_record_period_wrapped(kpi: Mapping[str, Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``record_period``.

    Re-export for clarity at the public surface. Computes the KPI

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_record_period")
    kwargs = {'kpi': kpi}
    try:
        result = record_period(**kwargs)
    except Exception as exc:
        return f"Tool c3_record_period failed: {exc}", {
            "c3_record_period": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_record_period: ok"
    return content, {
        "c3_record_period": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_make_history_wrapped(kpi_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``make_history``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_make_history")
    kwargs = {'kpi_id': kpi_id}
    try:
        result = make_history(**kwargs)
    except Exception as exc:
        return f"Tool c3_make_history failed: {exc}", {
            "c3_make_history": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_make_history: ok"
    return content, {
        "c3_make_history": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_evaluate_and_record_wrapped(kpi: Mapping[str, Any], dataframe: pd.DataFrame, history: KPIHistory) -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_and_record``.

    One-shot compute + record.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_evaluate_and_record")
    kwargs = {'kpi': kpi, 'dataframe': dataframe, 'history': history}
    try:
        result = evaluate_and_record(**kwargs)
    except Exception as exc:
        return f"Tool c3_evaluate_and_record failed: {exc}", {
            "c3_evaluate_and_record": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_evaluate_and_record: ok"
    return content, {
        "c3_evaluate_and_record": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_build_alarm_wrapped(kpi_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``build_alarm``.

    Build an alarm rule for a KPI.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_build_alarm")
    kwargs = {'kpi_id': kpi_id}
    try:
        result = build_alarm(**kwargs)
    except Exception as exc:
        return f"Tool c3_build_alarm failed: {exc}", {
            "c3_build_alarm": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_build_alarm: ok"
    return content, {
        "c3_build_alarm": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_check_alarm_wrapped(rule: AlarmRule) -> Tuple[str, dict]:
    """Tool wrapper for ``check_alarm``.

    Evaluate ``rule`` against a history window.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_check_alarm")
    kwargs = {'rule': rule}
    try:
        result = check_alarm(**kwargs)
    except Exception as exc:
        return f"Tool c3_check_alarm failed: {exc}", {
            "c3_check_alarm": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_check_alarm: ok"
    return content, {
        "c3_check_alarm": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def c3_sparkline_points_wrapped(values: Sequence[float], n: int) -> Tuple[str, dict]:
    """Tool wrapper for ``sparkline_points``.

    Downsample a series into ``n`` evenly-spaced points for UI.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c3_sparkline_points")
    kwargs = {'values': values, 'n': n}
    try:
        result = sparkline_points(**kwargs)
    except Exception as exc:
        return f"Tool c3_sparkline_points failed: {exc}", {
            "c3_sparkline_points": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c3_sparkline_points: ok"
    return content, {
        "c3_sparkline_points": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


C3_TOOLS = [
    c3_define_kpi_wrapped,
    c3_evaluate_python_code_wrapped,
    c3_compute_schedule_wrapped,
    c3_record_period_wrapped,
    c3_make_history_wrapped,
    c3_evaluate_and_record_wrapped,
    c3_build_alarm_wrapped,
    c3_check_alarm_wrapped,
    c3_sparkline_points_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_c3_kpi_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the C3 agent."""
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
        tools=C3_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR C3")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the C3 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING C3 RESULTS")
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


class C3Agent(BaseAgent):
    """OO wrapper for the C3 agent (node type ``kpi.compute``)."""

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
        return make_c3_kpi_agent(**self._params)

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
    "C3Agent",
    "make_c3_kpi_agent",
    "C3_TOOLS",
]
