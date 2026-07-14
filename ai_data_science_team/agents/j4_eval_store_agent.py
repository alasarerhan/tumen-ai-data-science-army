"""J4 Agent.

Phase-5 agent wrapper for spec J4.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.j4_eval_store``) with
LangChain ``@tool`` decorators and exposes the standard
``make_j4_eval_store_agent`` factory + ``J4Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``evaluation.store``
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

from ai_data_science_team.tools.j4_eval_store import (
    EvalRecord,
    EvalStore,
    SliceMetrics,
    compare_models,
    query_evaluations,
    record_evaluation,
    slice_by_feature,
    summarise_over_datasets,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "j4_agent"
NODE_TYPE = "evaluation.store"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def j4_record_evaluation_wrapped(store: EvalStore) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": EvalRecord,
    "content": str,
}]:
    """Tool wrapper for ``record_evaluation``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j4_record_evaluation")
    kwargs = {'store': store}
    try:
        result = record_evaluation(**kwargs)
    except Exception as exc:
        return f"Tool j4_record_evaluation failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"j4_record_evaluation: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j4_query_evaluations_wrapped(store: EvalStore) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": List[EvalRecord],
    "content": str,
}]:
    """Tool wrapper for ``query_evaluations``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j4_query_evaluations")
    kwargs = {'store': store}
    try:
        result = query_evaluations(**kwargs)
    except Exception as exc:
        return f"Tool j4_query_evaluations failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"j4_query_evaluations: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j4_compare_models_wrapped(store: EvalStore, model_ids: Sequence[str], dataset_id: str, metrics: Sequence[str]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, Dict[str, float]],
    "content": str,
}]:
    """Tool wrapper for ``compare_models``.

    Build a {model_id: {metric: value}} comparison dict on a

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j4_compare_models")
    kwargs = {'store': store, 'model_ids': model_ids, 'dataset_id': dataset_id, 'metrics': metrics}
    try:
        result = compare_models(**kwargs)
    except Exception as exc:
        return f"Tool j4_compare_models failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"j4_compare_models: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j4_summarise_over_datasets_wrapped(store: EvalStore, model_id: str, metric: str) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, float],
    "content": str,
}]:
    """Tool wrapper for ``summarise_over_datasets``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j4_summarise_over_datasets")
    kwargs = {'store': store, 'model_id': model_id, 'metric': metric}
    try:
        result = summarise_over_datasets(**kwargs)
    except Exception as exc:
        return f"Tool j4_summarise_over_datasets failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"j4_summarise_over_datasets: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def j4_slice_by_feature_wrapped(store: EvalStore) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, Dict[str, float]],
    "content": str,
}]:
    """Tool wrapper for ``slice_by_feature``.

    Return aggregated metric values for each slice, optionally

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j4_slice_by_feature")
    kwargs = {'store': store}
    try:
        result = slice_by_feature(**kwargs)
    except Exception as exc:
        return f"Tool j4_slice_by_feature failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"j4_slice_by_feature: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }



J4_TOOLS = [
    j4_record_evaluation_wrapped,
    j4_query_evaluations_wrapped,
    j4_compare_models_wrapped,
    j4_summarise_over_datasets_wrapped,
    j4_slice_by_feature_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_j4_eval_store_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J4 agent."""
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
        tools=J4_TOOLS,
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
        messages = [("system", "You are the J4 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING J4 RESULTS")
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


class J4Agent(BaseAgent):
    """OO wrapper for the J4 agent (node type ``evaluation.store``)."""

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
        return make_j4_eval_store_agent(**self._params)

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
    "J4Agent",
    "make_j4_eval_store_agent",
    "J4_TOOLS",
]
