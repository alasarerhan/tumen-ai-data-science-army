"""E1 Agent.

Phase-5 agent wrapper for spec E1.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.e1_multi_engine_trainer``) with
LangChain ``@tool`` decorators and exposes the standard
``make_e1_multi_engine_trainer_agent`` factory + ``E1Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.train``
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
from typing import Dict, Optional, Sequence, Mapping
from sklearn.pipeline import Pipeline

from ai_data_science_team.tools.e1_multi_engine_trainer import (
    CVResult,
    build_pipeline,
    candidates_for_task,
    cross_validate_candidates,
    select_best_model,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "e1_agent"
NODE_TYPE = "model.train"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def e1_candidates_for_task_wrapped(task_type: str, engine: str) -> Tuple[str, dict]:
    """Tool wrapper for ``candidates_for_task``.

    Return the class name for the candidate model of ``engine``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e1_candidates_for_task")
    kwargs = {'task_type': task_type, 'engine': engine}
    try:
        result = candidates_for_task(**kwargs)
    except Exception as exc:
        return f"Tool e1_candidates_for_task failed: {exc}", {
            "e1_candidates_for_task": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e1_candidates_for_task: ok"
    return content, {
        "e1_candidates_for_task": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e1_build_pipeline_wrapped(X: pd.DataFrame, task_type: str, engine: str, engine_params: Optional[Mapping[str, Any]]) -> Tuple[str, dict]:
    """Tool wrapper for ``build_pipeline``.

    Build a sklearn Pipeline imputer+scaler+OHE → estimator.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e1_build_pipeline")
    kwargs = {'X': X, 'task_type': task_type, 'engine': engine, 'engine_params': engine_params}
    try:
        result = build_pipeline(**kwargs)
    except Exception as exc:
        return f"Tool e1_build_pipeline failed: {exc}", {
            "e1_build_pipeline": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e1_build_pipeline: ok"
    return content, {
        "e1_build_pipeline": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e1_cross_validate_candidates_wrapped(X: pd.DataFrame, y: pd.Series, task_type: str, candidates: Optional[Sequence[str]], engine_params: Optional[Mapping[str, Any]], cv: Optional[Mapping[str, Any]]) -> Tuple[str, dict]:
    """Tool wrapper for ``cross_validate_candidates``.

    Run cross-validation for each engine in ``candidates``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e1_cross_validate_candidates")
    kwargs = {'X': X, 'y': y, 'task_type': task_type, 'candidates': candidates, 'engine_params': engine_params, 'cv': cv}
    try:
        result = cross_validate_candidates(**kwargs)
    except Exception as exc:
        return f"Tool e1_cross_validate_candidates failed: {exc}", {
            "e1_cross_validate_candidates": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e1_cross_validate_candidates: ok"
    return content, {
        "e1_cross_validate_candidates": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e1_select_best_model_wrapped(cv_output: Mapping[str, Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``select_best_model``.

    Pick the highest-scoring engine from a ``cross_validate_candidates`` output.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e1_select_best_model")
    kwargs = {'cv_output': cv_output}
    try:
        result = select_best_model(**kwargs)
    except Exception as exc:
        return f"Tool e1_select_best_model failed: {exc}", {
            "e1_select_best_model": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e1_select_best_model: ok"
    return content, {
        "e1_select_best_model": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


E1_TOOLS = [
    e1_candidates_for_task_wrapped,
    e1_build_pipeline_wrapped,
    e1_cross_validate_candidates_wrapped,
    e1_select_best_model_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_e1_multi_engine_trainer_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the E1 agent."""
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
        tools=E1_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR E1")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the E1 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING E1 RESULTS")
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


class E1Agent(BaseAgent):
    """OO wrapper for the E1 agent (node type ``model.train``)."""

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
        return make_e1_multi_engine_trainer_agent(**self._params)

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
    "E1Agent",
    "make_e1_multi_engine_trainer_agent",
    "E1_TOOLS",
]
