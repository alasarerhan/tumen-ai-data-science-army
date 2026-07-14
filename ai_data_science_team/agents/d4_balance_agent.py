"""D4 Agent.

Phase-5 agent wrapper for spec D4.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.d4_balance``) with
LangChain ``@tool`` decorators and exposes the standard
``make_d4_balance_agent`` factory + ``D4Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.balance``
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

from typing import List, Dict, Sequence

from ai_data_science_team.tools.d4_balance import (
    ClassDistribution,
    PRAUCRecommendation,
    SamplingReport,
    apply_strategy,
    balance_payload,
    class_distribution,
    class_weight,
    estimate_strategy_impact,
    is_imbalanced,
    recommend_metrics,
    select_strategy,
    undersample_indices,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "d4_balance_agent"
NODE_TYPE = "model.balance"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def d4_class_distribution_wrapped(y: Sequence[Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``class_distribution``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_class_distribution")
    kwargs = {'y': y}
    try:
        result = class_distribution(**kwargs)
    except Exception as exc:
        return f"Tool d4_class_distribution failed: {exc}", {
            "d4_class_distribution": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_class_distribution: ok"
    return content, {
        "d4_class_distribution": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_is_imbalanced_wrapped(dist: ClassDistribution) -> Tuple[str, dict]:
    """Tool wrapper for ``is_imbalanced``.

    Return a verdict + suggested severity.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_is_imbalanced")
    kwargs = {'dist': dist}
    try:
        result = is_imbalanced(**kwargs)
    except Exception as exc:
        return f"Tool d4_is_imbalanced failed: {exc}", {
            "d4_is_imbalanced": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_is_imbalanced: ok"
    return content, {
        "d4_is_imbalanced": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_select_strategy_wrapped(dist: ClassDistribution) -> Tuple[str, dict]:
    """Tool wrapper for ``select_strategy``.

    Heuristic strategy selector.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_select_strategy")
    kwargs = {'dist': dist}
    try:
        result = select_strategy(**kwargs)
    except Exception as exc:
        return f"Tool d4_select_strategy failed: {exc}", {
            "d4_select_strategy": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_select_strategy: ok"
    return content, {
        "d4_select_strategy": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_estimate_strategy_impact_wrapped(dist: ClassDistribution, strategy: str) -> Tuple[str, dict]:
    """Tool wrapper for ``estimate_strategy_impact``.

    Project how the strategy will reshape the distribution.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_estimate_strategy_impact")
    kwargs = {'dist': dist, 'strategy': strategy}
    try:
        result = estimate_strategy_impact(**kwargs)
    except Exception as exc:
        return f"Tool d4_estimate_strategy_impact failed: {exc}", {
            "d4_estimate_strategy_impact": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_estimate_strategy_impact: ok"
    return content, {
        "d4_estimate_strategy_impact": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_recommend_metrics_wrapped(dist: ClassDistribution) -> Tuple[str, dict]:
    """Tool wrapper for ``recommend_metrics``.

    For imbalanced classification, recommend PR-AUC primary

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_recommend_metrics")
    kwargs = {'dist': dist}
    try:
        result = recommend_metrics(**kwargs)
    except Exception as exc:
        return f"Tool d4_recommend_metrics failed: {exc}", {
            "d4_recommend_metrics": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_recommend_metrics: ok"
    return content, {
        "d4_recommend_metrics": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_undersample_indices_wrapped(y: Sequence[Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``undersample_indices``.

    Return indices after majority-class undersampling so that

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_undersample_indices")
    kwargs = {'y': y}
    try:
        result = undersample_indices(**kwargs)
    except Exception as exc:
        return f"Tool d4_undersample_indices failed: {exc}", {
            "d4_undersample_indices": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_undersample_indices: ok"
    return content, {
        "d4_undersample_indices": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_class_weight_wrapped(y: Sequence[Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``class_weight``.

    Inverse-frequency weights, normalised to sum to n_classes.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_class_weight")
    kwargs = {'y': y}
    try:
        result = class_weight(**kwargs)
    except Exception as exc:
        return f"Tool d4_class_weight failed: {exc}", {
            "d4_class_weight": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_class_weight: ok"
    return content, {
        "d4_class_weight": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_apply_strategy_wrapped(y: Sequence[Any], strategy: str) -> Tuple[str, dict]:
    """Tool wrapper for ``apply_strategy``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_apply_strategy")
    kwargs = {'y': y, 'strategy': strategy}
    try:
        result = apply_strategy(**kwargs)
    except Exception as exc:
        return f"Tool d4_apply_strategy failed: {exc}", {
            "d4_apply_strategy": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_apply_strategy: ok"
    return content, {
        "d4_apply_strategy": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def d4_balance_payload_wrapped(dist: ClassDistribution) -> Tuple[str, dict]:
    """Tool wrapper for ``balance_payload``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d4_balance_payload")
    kwargs = {'dist': dist}
    try:
        result = balance_payload(**kwargs)
    except Exception as exc:
        return f"Tool d4_balance_payload failed: {exc}", {
            "d4_balance_payload": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d4_balance_payload: ok"
    return content, {
        "d4_balance_payload": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


D4_TOOLS = [
    d4_class_distribution_wrapped,
    d4_is_imbalanced_wrapped,
    d4_select_strategy_wrapped,
    d4_estimate_strategy_impact_wrapped,
    d4_recommend_metrics_wrapped,
    d4_undersample_indices_wrapped,
    d4_class_weight_wrapped,
    d4_apply_strategy_wrapped,
    d4_balance_payload_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_d4_balance_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the D4 agent."""
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
        tools=D4_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR D4")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the D4 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING D4 RESULTS")
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


class D4Agent(BaseAgent):
    """OO wrapper for the D4 agent (node type ``model.balance``)."""

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
        return make_d4_balance_agent(**self._params)

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
    "D4Agent",
    "make_d4_balance_agent",
    "D4_TOOLS",
]
