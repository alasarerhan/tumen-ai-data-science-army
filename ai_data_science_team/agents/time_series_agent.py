from __future__ import annotations

"""E11 Agent.

Phase-5 agent wrapper for spec E11.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.time_series``) with
LangChain ``@tool`` decorators and exposes the standard
``make_time_series_agent`` factory + ``E11Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.train.timeseries``
"""

from typing import (Dict, Iterable, Mapping, Optional, Tuple)  # noqa: E402
import logging  # noqa: E402, F401
from typing import Any  # noqa: E402, F401

from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, Sequence, TypedDict  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401

from ai_data_science_team.tools.e11_time_series import (  # noqa: E402, F401
    build_panel,
    holiday_calendar,
    moving_average_forecast,
    multiplicative_seasonal_forecast,
    reconcile_top_down,
    seasonal_naive_forecast,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "time_series_agent"
NODE_TYPE = "model.train.timeseries"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def seasonal_naive_forecast_wrapped(history: Sequence[float], horizon: int, period: int) -> Tuple[str, dict]:
    """Tool wrapper for ``seasonal_naive_forecast``.

    Repeat the last ``period`` window ``horizon`` times.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e11_seasonal_naive_forecast")
    kwargs = {'history': history, 'horizon': horizon, 'period': period}
    try:
        result = seasonal_naive_forecast(**kwargs)
    except Exception as exc:
        return f"Tool e11_seasonal_naive_forecast failed: {exc}", {
            "seasonal_naive_forecast": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e11_seasonal_naive_forecast: ok"
    return content, {
        "seasonal_naive_forecast": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def moving_average_forecast_wrapped(history: Sequence[float], horizon: int, window: int) -> Tuple[str, dict]:
    """Tool wrapper for ``moving_average_forecast``.

    Slide a window over the trailing ``window`` observations.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e11_moving_average_forecast")
    kwargs = {'history': history, 'horizon': horizon, 'window': window}
    try:
        result = moving_average_forecast(**kwargs)
    except Exception as exc:
        return f"Tool e11_moving_average_forecast failed: {exc}", {
            "moving_average_forecast": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e11_moving_average_forecast: ok"
    return content, {
        "moving_average_forecast": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def multiplicative_seasonal_forecast_wrapped(history: Sequence[float], horizon: int, period: int) -> Tuple[str, dict]:
    """Tool wrapper for ``multiplicative_seasonal_forecast``.

    Forecast = global mean × season-index of the most-recent season.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e11_multiplicative_seasonal_forecast")
    kwargs = {'history': history, 'horizon': horizon, 'period': period}
    try:
        result = multiplicative_seasonal_forecast(**kwargs)
    except Exception as exc:
        return f"Tool e11_multiplicative_seasonal_forecast failed: {exc}", {
            "multiplicative_seasonal_forecast": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e11_multiplicative_seasonal_forecast: ok"
    return content, {
        "multiplicative_seasonal_forecast": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def reconcile_top_down_wrapped(parent_forecast: float, child_histories: Mapping[Any, Sequence[float]]) -> Tuple[str, dict]:
    """Tool wrapper for ``reconcile_top_down``.

    Top-down reconciliation: each child gets its historical share

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e11_reconcile_top_down")
    kwargs = {'parent_forecast': parent_forecast, 'child_histories': child_histories}
    try:
        result = reconcile_top_down(**kwargs)
    except Exception as exc:
        return f"Tool e11_reconcile_top_down failed: {exc}", {
            "reconcile_top_down": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e11_reconcile_top_down: ok"
    return content, {
        "reconcile_top_down": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def holiday_calendar_wrapped(country: str, years: Iterable[int]) -> Tuple[str, dict]:
    """Tool wrapper for ``holiday_calendar``.

    Return the list of fixed-date holidays for ``country`` across

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e11_holiday_calendar")
    kwargs = {'country': country, 'years': years}
    try:
        result = holiday_calendar(**kwargs)
    except Exception as exc:
        return f"Tool e11_holiday_calendar failed: {exc}", {
            "holiday_calendar": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e11_holiday_calendar: ok"
    return content, {
        "holiday_calendar": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def build_panel_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``build_panel``.

    Normalise a raw frame into a long panel (group × ds × y) with

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e11_build_panel")
    kwargs = {'df': df}
    try:
        result = build_panel(**kwargs)
    except Exception as exc:
        return f"Tool e11_build_panel failed: {exc}", {
            "build_panel": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e11_build_panel: ok"
    return content, {
        "build_panel": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


TIME_SERIES_TOOLS = [
    seasonal_naive_forecast_wrapped,
    moving_average_forecast_wrapped,
    multiplicative_seasonal_forecast_wrapped,
    reconcile_top_down_wrapped,
    holiday_calendar_wrapped,
    build_panel_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_time_series_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the E11 agent."""
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    from langchain.agents import create_agent  # noqa: E402, F401

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=TIME_SERIES_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR E11")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the E11 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING E11 RESULTS")
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


class TimeSeriesForecastAgent(BaseAgent):
    """OO wrapper for the E11 agent (node type ``model.train.timeseries``)."""

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
        return make_time_series_agent(**self._params)

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
        from IPython.display import Markdown as _Markdown  # noqa: E402, F401
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
    "TimeSeriesForecastAgent",
    "make_time_series_agent",
    "TIME_SERIES_TOOLS",
]
