from __future__ import annotations

"""G4 Agent.

Phase-5 agent wrapper for spec G4.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.batch_scoring``) with
LangChain ``@tool`` decorators and exposes the standard
``make_batch_scoring_agent`` factory + ``G4Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``deploy.batch_score``
"""

from typing import (Dict, Optional, Tuple)  # noqa: E402
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


from ai_data_science_team.tools.batch_scoring import (  # noqa: E402, F401
    align_features,
    chunked_predict,
    predict_dataframe,
    resolve_model,
    scoring_report,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "batch_scoring_agent"
NODE_TYPE = "deploy.batch_score"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def align_features_wrapped(df: pd.DataFrame, expected_features: Sequence[str]) -> Tuple[str, dict]:
    """Tool wrapper for ``align_features``.

    Align ``df`` columns to ``expected_features``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g4_align_features")
    kwargs = {'df': df, 'expected_features': expected_features}
    try:
        result = align_features(**kwargs)
    except Exception as exc:
        return f"Tool g4_align_features failed: {exc}", {
            "align_features": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g4_align_features: ok"
    return content, {
        "align_features": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def resolve_model_wrapped(model: Any) -> Tuple[str, dict]:
    """Tool wrapper for ``resolve_model``.

    Pass through an already-loaded model.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g4_resolve_model")
    kwargs = {'model': model}
    try:
        result = resolve_model(**kwargs)
    except Exception as exc:
        return f"Tool g4_resolve_model failed: {exc}", {
            "resolve_model": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g4_resolve_model: ok"
    return content, {
        "resolve_model": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def predict_dataframe_wrapped(df: pd.DataFrame, model: Any) -> Tuple[str, dict]:
    """Tool wrapper for ``predict_dataframe``.

    Score ``df`` with ``model``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g4_predict_dataframe")
    kwargs = {'df': df, 'model': model}
    try:
        result = predict_dataframe(**kwargs)
    except Exception as exc:
        return f"Tool g4_predict_dataframe failed: {exc}", {
            "predict_dataframe": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g4_predict_dataframe: ok"
    return content, {
        "predict_dataframe": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def chunked_predict_wrapped(df: pd.DataFrame, model: Any) -> Tuple[str, dict]:
    """Tool wrapper for ``chunked_predict``.

    Apply :func:`predict_dataframe` to ``df`` in chunks.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g4_chunked_predict")
    kwargs = {'df': df, 'model': model}
    try:
        result = chunked_predict(**kwargs)
    except Exception as exc:
        return f"Tool g4_chunked_predict failed: {exc}", {
            "chunked_predict": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g4_chunked_predict: ok"
    return content, {
        "chunked_predict": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def scoring_report_wrapped(n_rows: int, duration_s: float, model_uri: str) -> Tuple[str, dict]:
    """Tool wrapper for ``scoring_report``.

    Wrap scoring stats into the spec's ``scoring_report`` shape.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g4_scoring_report")
    kwargs = {'n_rows': n_rows, 'duration_s': duration_s, 'model_uri': model_uri}
    try:
        result = scoring_report(**kwargs)
    except Exception as exc:
        return f"Tool g4_scoring_report failed: {exc}", {
            "scoring_report": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g4_scoring_report: ok"
    return content, {
        "scoring_report": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


BATCH_SCORING_TOOLS = [
    align_features_wrapped,
    resolve_model_wrapped,
    predict_dataframe_wrapped,
    chunked_predict_wrapped,
    scoring_report_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_batch_scoring_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the G4 agent."""
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
        tools=BATCH_SCORING_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR G4")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the G4 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING G4 RESULTS")
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


class BatchScoringAgent(BaseAgent):
    """OO wrapper for the G4 agent (node type ``deploy.batch_score``)."""

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
        return make_batch_scoring_agent(**self._params)

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
    "BatchScoringAgent",
    "make_batch_scoring_agent",
    "BATCH_SCORING_TOOLS",
]
