"""A4 Agent.

Phase-5 agent wrapper for spec A4.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.a4_hypothesis_testing``) with
LangChain ``@tool`` decorators and exposes the standard
``make_a4_hypothesis_testing_agent`` factory + ``A4Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.hypothesis_test``
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

from typing import Dict, Sequence

from ai_data_science_team.tools.a4_hypothesis_testing import (
    A4_HYPOTHESIS_TESTING_TOOL_NAMES,
    HypothesisTestResult,
    TestRecommendation,
    interpret_result,
    recommend_test,
    run_test,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "a4_agent"
NODE_TYPE = "model.hypothesis_test"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def a4_recommend_test_wrapped(values: Sequence[float]) -> Tuple[str, dict]:
    """Tool wrapper for ``recommend_test``.

    Pick a hypothesis test for the data shape.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a4_recommend_test")
    kwargs = {'values': values}
    try:
        result = recommend_test(**kwargs)
    except Exception as exc:
        return f"Tool a4_recommend_test failed: {exc}", {
            "a4_recommend_test": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"a4_recommend_test: ok"
    return content, {
        "a4_recommend_test": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def a4_run_test_wrapped(values: Sequence[float]) -> Tuple[str, dict]:
    """Tool wrapper for ``run_test``.

    Execute the chosen hypothesis test (after :func:`recommend_test`).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a4_run_test")
    kwargs = {'values': values}
    try:
        result = run_test(**kwargs)
    except Exception as exc:
        return f"Tool a4_run_test failed: {exc}", {
            "a4_run_test": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"a4_run_test: ok"
    return content, {
        "a4_run_test": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def a4_interpret_result_wrapped(p_value: float, effect_size: float) -> Tuple[str, dict]:
    """Tool wrapper for ``interpret_result``.

    Translate a p_value + effect_size into a plain-language finding.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: a4_interpret_result")
    kwargs = {'p_value': p_value, 'effect_size': effect_size}
    try:
        result = interpret_result(**kwargs)
    except Exception as exc:
        return f"Tool a4_interpret_result failed: {exc}", {
            "a4_interpret_result": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"a4_interpret_result: ok"
    return content, {
        "a4_interpret_result": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }



A4_TOOLS = [
    a4_recommend_test_wrapped,
    a4_run_test_wrapped,
    a4_interpret_result_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_a4_hypothesis_testing_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the A4 agent."""
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
        tools=A4_TOOLS,
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
        logger.info(f"    * RUN REACT AGENT FOR A4")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the A4 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING A4 RESULTS")
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


class A4Agent(BaseAgent):
    """OO wrapper for the A4 agent (node type ``model.hypothesis_test``)."""

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
        return make_a4_hypothesis_testing_agent(**self._params)

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
    "A4Agent",
    "make_a4_hypothesis_testing_agent",
    "A4_TOOLS",
]
