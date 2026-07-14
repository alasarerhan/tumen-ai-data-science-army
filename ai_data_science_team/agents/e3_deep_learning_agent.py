"""E3 Agent.

Phase-5 agent wrapper for spec E3.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.e3_deep_learning``) with
LangChain ``@tool`` decorators and exposes the standard
``make_e3_deep_learning_agent`` factory + ``E3Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.train.deep``
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
from typing import Dict, Optional, Any, Sequence

from ai_data_science_team.tools.e3_deep_learning import (
    E3_DEEP_LEARNING_TOOL_NAMES,
    build_lstm_classifier,
    build_lstm_forecaster,
    build_mlp_classifier,
    build_mlp_regressor,
    detect_device,
    train_lstm_forecaster,
    train_mlp_classifier,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "e3_agent"
NODE_TYPE = "model.train.deep"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def e3_detect_device_wrapped(prefer: Optional[str]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": str,
    "content": str,
}]:
    """Tool wrapper for ``detect_device``.

    Return one of ``"cuda"``, ``"mps"``, ``"cpu"`` based on availability.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_detect_device")
    kwargs = {'prefer': prefer}
    try:
        result = detect_device(**kwargs)
    except Exception as exc:
        return f"Tool e3_detect_device failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_detect_device: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e3_build_mlp_classifier_wrapped(n_features: int, n_classes: int, hidden: Sequence[int], dropout: float) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Any,
    "content": str,
}]:
    """Tool wrapper for ``build_mlp_classifier``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_build_mlp_classifier")
    kwargs = {'n_features': n_features, 'n_classes': n_classes, 'hidden': hidden, 'dropout': dropout}
    try:
        result = build_mlp_classifier(**kwargs)
    except Exception as exc:
        return f"Tool e3_build_mlp_classifier failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_build_mlp_classifier: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e3_build_mlp_regressor_wrapped(n_features: int, hidden: Sequence[int], dropout: float) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Any,
    "content": str,
}]:
    """Tool wrapper for ``build_mlp_regressor``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_build_mlp_regressor")
    kwargs = {'n_features': n_features, 'hidden': hidden, 'dropout': dropout}
    try:
        result = build_mlp_regressor(**kwargs)
    except Exception as exc:
        return f"Tool e3_build_mlp_regressor failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_build_mlp_regressor: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e3_build_lstm_forecaster_wrapped(n_features: int, hidden: int, layers: int, horizon: int) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Any,
    "content": str,
}]:
    """Tool wrapper for ``build_lstm_forecaster``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_build_lstm_forecaster")
    kwargs = {'n_features': n_features, 'hidden': hidden, 'layers': layers, 'horizon': horizon}
    try:
        result = build_lstm_forecaster(**kwargs)
    except Exception as exc:
        return f"Tool e3_build_lstm_forecaster failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_build_lstm_forecaster: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e3_build_lstm_classifier_wrapped(n_features: int, n_classes: int, hidden: int, layers: int) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Any,
    "content": str,
}]:
    """Tool wrapper for ``build_lstm_classifier``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_build_lstm_classifier")
    kwargs = {'n_features': n_features, 'n_classes': n_classes, 'hidden': hidden, 'layers': layers}
    try:
        result = build_lstm_classifier(**kwargs)
    except Exception as exc:
        return f"Tool e3_build_lstm_classifier failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_build_lstm_classifier: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e3_train_mlp_classifier_wrapped(X: np.ndarray, y: np.ndarray) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, Any],
    "content": str,
}]:
    """Tool wrapper for ``train_mlp_classifier``.

    Train an MLP classifier (or regressor) with early stopping.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_train_mlp_classifier")
    kwargs = {'X': X, 'y': y}
    try:
        result = train_mlp_classifier(**kwargs)
    except Exception as exc:
        return f"Tool e3_train_mlp_classifier failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_train_mlp_classifier: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def e3_train_lstm_forecaster_wrapped(X: np.ndarray, y: np.ndarray) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, Any],
    "content": str,
}]:
    """Tool wrapper for ``train_lstm_forecaster``.

    Train an LSTM forecaster on (X, y) where X is (B, T, F).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e3_train_lstm_forecaster")
    kwargs = {'X': X, 'y': y}
    try:
        result = train_lstm_forecaster(**kwargs)
    except Exception as exc:
        return f"Tool e3_train_lstm_forecaster failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"e3_train_lstm_forecaster: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }



E3_TOOLS = [
    e3_detect_device_wrapped,
    e3_build_mlp_classifier_wrapped,
    e3_build_mlp_regressor_wrapped,
    e3_build_lstm_forecaster_wrapped,
    e3_build_lstm_classifier_wrapped,
    e3_train_mlp_classifier_wrapped,
    e3_train_lstm_forecaster_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_e3_deep_learning_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the E3 agent."""
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
        tools=E3_TOOLS,
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
        messages = [("system", "You are the E3 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING E3 RESULTS")
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


class E3Agent(BaseAgent):
    """OO wrapper for the E3 agent (node type ``model.train.deep``)."""

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
        return make_e3_deep_learning_agent(**self._params)

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
    "E3Agent",
    "make_e3_deep_learning_agent",
    "E3_TOOLS",
]
