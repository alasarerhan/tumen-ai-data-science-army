from __future__ import annotations

"""B5 Agent.

Phase-5 agent wrapper for spec B5.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.pii``) with
LangChain ``@tool`` decorators and exposes the standard
``make_pii_agent`` factory + ``B5Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``data.pii_anonymize``
"""

import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Dict,
    Mapping,  # noqa: E402, F401
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
from ai_data_science_team.tools.pii import (  # noqa: E402, F401
    PIIScanReport,
    anonymize_dataframe,
    default_strategies_for,
    scan_pii,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "pii_agent"
NODE_TYPE = "data.pii_anonymize"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def scan_pii_wrapped(df: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``scan_pii``.

    Detect PII columns in a DataFrame.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b5_scan_pii")
    kwargs = {"df": df}
    try:
        result = scan_pii(**kwargs)
    except Exception as exc:
        return f"Tool b5_scan_pii failed: {exc}", {
            "scan_pii": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "b5_scan_pii: ok"
    return content, {
        "scan_pii": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def default_strategies_for_wrapped(scan: PIIScanReport) -> Tuple[str, dict]:
    """Tool wrapper for ``default_strategies_for``.

    Return default per-column strategies derived from a scan.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b5_default_strategies_for")
    kwargs = {"scan": scan}
    try:
        result = default_strategies_for(**kwargs)
    except Exception as exc:
        return f"Tool b5_default_strategies_for failed: {exc}", {
            "default_strategies_for": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "b5_default_strategies_for: ok"
    return content, {
        "default_strategies_for": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def anonymize_dataframe_wrapped(
    df: pd.DataFrame, strategies: Mapping[str, Mapping[str, Any]]
) -> Tuple[str, dict]:
    """Tool wrapper for ``anonymize_dataframe``.

    Apply per-column anonymisation strategies.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b5_anonymize_dataframe")
    kwargs = {"df": df, "strategies": strategies}
    try:
        result = anonymize_dataframe(**kwargs)
    except Exception as exc:
        return f"Tool b5_anonymize_dataframe failed: {exc}", {
            "anonymize_dataframe": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "b5_anonymize_dataframe: ok"
    return content, {
        "anonymize_dataframe": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


PII_ANONYMIZATION_TOOLS = [
    scan_pii_wrapped,
    default_strategies_for_wrapped,
    anonymize_dataframe_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_pii_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the B5 agent."""
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
        tools=PII_ANONYMIZATION_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR B5")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the B5 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING B5 RESULTS")
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


class PIIAnonymizationAgent(BaseAgent):
    """OO wrapper for the B5 agent (node type ``data.pii_anonymize``)."""

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
        return make_pii_agent(**self._params)

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
    "PIIAnonymizationAgent",
    "make_pii_agent",
    "PII_ANONYMIZATION_TOOLS",
]
