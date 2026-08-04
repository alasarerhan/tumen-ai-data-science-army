from __future__ import annotations

"""C1 Agent.

Phase-5 agent wrapper for spec C1.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.insight``) with
LangChain ``@tool`` decorators and exposes the standard
``make_insight_agent`` factory + ``C1Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``insight.mine``
"""

import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Dict,
    Optional,
    Tuple,
)

import pandas as pd  # noqa: E402, F401
from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, Sequence, TypedDict  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.insight import (  # noqa: E402, F401
    find_anomalies,
    find_class_imbalance,
    find_constants_and_outliers,
    find_missing_patterns,
    find_skewness,
    find_strong_correlations,
    mine_insights,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "insight_agent"
NODE_TYPE = "insight.mine"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def find_anomalies_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``find_anomalies``.

    Return insights for columns whose values are extreme z-scores.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_find_anomalies")
    kwargs = {"df": df}
    try:
        result = find_anomalies(**kwargs)
    except Exception as exc:
        return f"Tool c1_find_anomalies failed: {exc}", {
            "find_anomalies": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_find_anomalies: ok"
    return content, {
        "find_anomalies": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def find_strong_correlations_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``find_strong_correlations``.

    Return insights for column pairs with |corr| ≥ threshold.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_find_strong_correlations")
    kwargs = {"df": df}
    try:
        result = find_strong_correlations(**kwargs)
    except Exception as exc:
        return f"Tool c1_find_strong_correlations failed: {exc}", {
            "find_strong_correlations": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_find_strong_correlations: ok"
    return content, {
        "find_strong_correlations": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def find_skewness_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``find_skewness``.

    Return insights for numeric columns with heavy skew.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_find_skewness")
    kwargs = {"df": df}
    try:
        result = find_skewness(**kwargs)
    except Exception as exc:
        return f"Tool c1_find_skewness failed: {exc}", {
            "find_skewness": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_find_skewness: ok"
    return content, {
        "find_skewness": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def find_missing_patterns_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``find_missing_patterns``.

    Return insights for columns with high null rate and

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_find_missing_patterns")
    kwargs = {"df": df}
    try:
        result = find_missing_patterns(**kwargs)
    except Exception as exc:
        return f"Tool c1_find_missing_patterns failed: {exc}", {
            "find_missing_patterns": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_find_missing_patterns: ok"
    return content, {
        "find_missing_patterns": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def find_class_imbalance_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``find_class_imbalance``.

    Flag low-cardinality columns with skewed class distribution.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_find_class_imbalance")
    kwargs = {"df": df}
    try:
        result = find_class_imbalance(**kwargs)
    except Exception as exc:
        return f"Tool c1_find_class_imbalance failed: {exc}", {
            "find_class_imbalance": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_find_class_imbalance: ok"
    return content, {
        "find_class_imbalance": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def find_constants_and_outliers_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``find_constants_and_outliers``.

    Single-value columns (zero variance) — useless for ML.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_find_constants_and_outliers")
    kwargs = {"df": df}
    try:
        result = find_constants_and_outliers(**kwargs)
    except Exception as exc:
        return f"Tool c1_find_constants_and_outliers failed: {exc}", {
            "find_constants_and_outliers": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_find_constants_and_outliers: ok"
    return content, {
        "find_constants_and_outliers": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def mine_insights_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``mine_insights``.

    Run the full insight pipeline and return the top insights.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c1_mine_insights")
    kwargs = {"df": df}
    try:
        result = mine_insights(**kwargs)
    except Exception as exc:
        return f"Tool c1_mine_insights failed: {exc}", {
            "mine_insights": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c1_mine_insights: ok"
    return content, {
        "mine_insights": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


INSIGHT_MINING_TOOLS = [
    find_anomalies_wrapped,
    find_strong_correlations_wrapped,
    find_skewness_wrapped,
    find_missing_patterns_wrapped,
    find_class_imbalance_wrapped,
    find_constants_and_outliers_wrapped,
    mine_insights_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_insight_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the C1 agent."""
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
        tools=INSIGHT_MINING_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR C1")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the C1 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING C1 RESULTS")
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
            name = getattr(getattr(msg, "tool_call_id", None), "name", None) or getattr(
                msg, "name", None
            )
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


class InsightMiningAgent(BaseAgent):
    """OO wrapper for the C1 agent (node type ``insight.mine``)."""

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
        return make_insight_agent(**self._params)

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
    "InsightMiningAgent",
    "make_insight_agent",
    "INSIGHT_MINING_TOOLS",
]
