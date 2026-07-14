"""E2 Agent.

Phase-5 agent wrapper for spec E2.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.e2_hpo``) with
LangChain ``@tool`` decorators and exposes the standard
``make_e2_hpo_agent`` factory + ``E2Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.hpo``
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

from typing import Dict, Optional, Mapping, Callable
import random

from ai_data_science_team.tools.e2_hpo import (
    E2_HPO_TOOL_NAMES,
    HPOResult,
    RandomSampler,
    TrialResult,
    random_sample_params,
    run_study,
    suggest_default_search_space,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "e2_agent"
NODE_TYPE = "model.hpo"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def e2_suggest_default_search_space_wrapped(engine: str, task_type: str) -> Tuple[str, dict]:
    """Tool wrapper for ``suggest_default_search_space``.

    Return the default search space for an ``(engine, task_type)`` pair.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e2_suggest_default_search_space")
    kwargs = {'engine': engine, 'task_type': task_type}
    try:
        result = suggest_default_search_space(**kwargs)
    except Exception as exc:
        return f"Tool e2_suggest_default_search_space failed: {exc}", {
            "e2_suggest_default_search_space": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e2_suggest_default_search_space: ok"
    return content, {
        "e2_suggest_default_search_space": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e2_random_sample_params_wrapped(space: Mapping[str, Mapping[str, Any]], rng: Optional[random.Random]) -> Tuple[str, dict]:
    """Tool wrapper for ``random_sample_params``.

    Sample a parameter dict from ``space``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e2_random_sample_params")
    kwargs = {'space': space, 'rng': rng}
    try:
        result = random_sample_params(**kwargs)
    except Exception as exc:
        return f"Tool e2_random_sample_params failed: {exc}", {
            "e2_random_sample_params": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e2_random_sample_params: ok"
    return content, {
        "e2_random_sample_params": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e2_run_study_wrapped(objective_fn: Callable[[Dict[str, Any]], float], space: Mapping[str, Mapping[str, Any]]) -> Tuple[str, dict]:
    """Tool wrapper for ``run_study``.

    Run an in-tree HPO study using ``RandomSampler`` by default.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e2_run_study")
    kwargs = {'objective_fn': objective_fn, 'space': space}
    try:
        result = run_study(**kwargs)
    except Exception as exc:
        return f"Tool e2_run_study failed: {exc}", {
            "e2_run_study": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e2_run_study: ok"
    return content, {
        "e2_run_study": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


E2_TOOLS = [
    e2_suggest_default_search_space_wrapped,
    e2_random_sample_params_wrapped,
    e2_run_study_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_e2_hpo_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the E2 agent."""
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
        tools=E2_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR E2")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the E2 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING E2 RESULTS")
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


class E2Agent(BaseAgent):
    """OO wrapper for the E2 agent (node type ``model.hpo``)."""

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
        return make_e2_hpo_agent(**self._params)

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
    "E2Agent",
    "make_e2_hpo_agent",
    "E2_TOOLS",
]
