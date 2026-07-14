"""F5 Agent.

Phase-5 agent wrapper for spec F5.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.f5_robustness``) with
LangChain ``@tool`` decorators and exposes the standard
``make_f5_robustness_agent`` factory + ``F5Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.robustness``
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

import numpy as np
from typing import List, Sequence, Callable

from ai_data_science_team.tools.f5_robustness import (
    RobustnessResult,
    Scenario,
    add_gaussian_noise,
    default_scenarios,
    evaluate_robustness,
    mask_features,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "f5_agent"
NODE_TYPE = "model.robustness"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def f5_add_gaussian_noise_wrapped(X: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``add_gaussian_noise``.

    Add N(0, sigma) noise to numeric columns of ``X``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f5_add_gaussian_noise")
    kwargs = {'X': X}
    try:
        result = add_gaussian_noise(**kwargs)
    except Exception as exc:
        return f"Tool f5_add_gaussian_noise failed: {exc}", {
            "f5_add_gaussian_noise": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"f5_add_gaussian_noise: ok"
    return content, {
        "f5_add_gaussian_noise": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f5_mask_features_wrapped(X: np.ndarray, mask_rate: float) -> Tuple[str, dict]:
    """Tool wrapper for ``mask_features``.

    Randomly mask ``mask_rate`` of cells to ``fill_value``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f5_mask_features")
    kwargs = {'X': X, 'mask_rate': mask_rate}
    try:
        result = mask_features(**kwargs)
    except Exception as exc:
        return f"Tool f5_mask_features failed: {exc}", {
            "f5_mask_features": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"f5_mask_features: ok"
    return content, {
        "f5_mask_features": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f5_default_scenarios_wrapped(sigma_levels: Sequence[float], mask_levels: Sequence[float]) -> Tuple[str, dict]:
    """Tool wrapper for ``default_scenarios``.

    Return the spec's default scenario set.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f5_default_scenarios")
    kwargs = {'sigma_levels': sigma_levels, 'mask_levels': mask_levels}
    try:
        result = default_scenarios(**kwargs)
    except Exception as exc:
        return f"Tool f5_default_scenarios failed: {exc}", {
            "f5_default_scenarios": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"f5_default_scenarios: ok"
    return content, {
        "f5_default_scenarios": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def f5_evaluate_robustness_wrapped(model_name: str, predict: Callable[[np.ndarray], np.ndarray], X: np.ndarray, y: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_robustness``.

    Run ``predict`` over each scenario ``replicates`` times.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: f5_evaluate_robustness")
    kwargs = {'model_name': model_name, 'predict': predict, 'X': X, 'y': y}
    try:
        result = evaluate_robustness(**kwargs)
    except Exception as exc:
        return f"Tool f5_evaluate_robustness failed: {exc}", {
            "f5_evaluate_robustness": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"f5_evaluate_robustness: ok"
    return content, {
        "f5_evaluate_robustness": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }



F5_TOOLS = [
    f5_add_gaussian_noise_wrapped,
    f5_mask_features_wrapped,
    f5_default_scenarios_wrapped,
    f5_evaluate_robustness_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_f5_robustness_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the F5 agent."""
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
        tools=F5_TOOLS,
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
        logger.info(f"    * RUN REACT AGENT FOR F5")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the F5 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING F5 RESULTS")
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


class F5Agent(BaseAgent):
    """OO wrapper for the F5 agent (node type ``model.robustness``)."""

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
        return make_f5_robustness_agent(**self._params)

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
    "F5Agent",
    "make_f5_robustness_agent",
    "F5_TOOLS",
]
