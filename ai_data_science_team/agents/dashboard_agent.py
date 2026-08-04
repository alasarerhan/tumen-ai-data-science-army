from __future__ import annotations

"""C2 Agent.

Phase-5 agent wrapper for spec C2.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.dashboard``) with
LangChain ``@tool`` decorators and exposes the standard
``make_dashboard_agent`` factory + ``C2Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``dashboard.compose``
"""

import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Dict,
    Mapping,  # noqa: E402
    Optional,
    Tuple,
)

from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, Sequence, TypedDict  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.dashboard import (  # noqa: E402, F401
    Dashboard,
    add_panel,
    make_dashboard,
    make_share_token,
    render_snapshot,
    validate_layout,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "dashboard_agent"
NODE_TYPE = "dashboard.compose"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def add_panel_wrapped(dashboard: Dashboard) -> Tuple[str, dict]:
    """Tool wrapper for ``add_panel``.

    Add a chart panel to a dashboard and return it.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c2_add_panel")
    kwargs = {"dashboard": dashboard}
    try:
        result = add_panel(**kwargs)
    except Exception as exc:
        return f"Tool c2_add_panel failed: {exc}", {
            "add_panel": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c2_add_panel: ok"
    return content, {
        "add_panel": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def validate_layout_wrapped(dashboard: Dashboard) -> Tuple[str, dict]:
    """Tool wrapper for ``validate_layout``.

    Return a list of layout issues (empty list = valid).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c2_validate_layout")
    kwargs = {"dashboard": dashboard}
    try:
        result = validate_layout(**kwargs)
    except Exception as exc:
        return f"Tool c2_validate_layout failed: {exc}", {
            "validate_layout": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c2_validate_layout: ok"
    return content, {
        "validate_layout": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def make_share_token_wrapped(dashboard: Dashboard) -> Tuple[str, dict]:
    """Tool wrapper for ``make_share_token``.

    Compute a deterministic share token from a dashboard snapshot.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c2_make_share_token")
    kwargs = {"dashboard": dashboard}
    try:
        result = make_share_token(**kwargs)
    except Exception as exc:
        return f"Tool c2_make_share_token failed: {exc}", {
            "make_share_token": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c2_make_share_token: ok"
    return content, {
        "make_share_token": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def render_snapshot_wrapped(dashboard: Dashboard) -> Tuple[str, dict]:
    """Tool wrapper for ``render_snapshot``.

    Render a deterministic textual snapshot of the dashboard.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c2_render_snapshot")
    kwargs = {"dashboard": dashboard}
    try:
        result = render_snapshot(**kwargs)
    except Exception as exc:
        return f"Tool c2_render_snapshot failed: {exc}", {
            "render_snapshot": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c2_render_snapshot: ok"
    return content, {
        "render_snapshot": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def make_dashboard_wrapped(name: str, panels: Sequence[Mapping[str, Any]]) -> Tuple[str, dict]:
    """Tool wrapper for ``make_dashboard``.

    One-shot constructor that materialises a dashboard from a list

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c2_make_dashboard")
    kwargs = {"name": name, "panels": panels}
    try:
        result = make_dashboard(**kwargs)
    except Exception as exc:
        return f"Tool c2_make_dashboard failed: {exc}", {
            "make_dashboard": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c2_make_dashboard: ok"
    return content, {
        "make_dashboard": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


DASHBOARD_COMPOSER_TOOLS = [
    add_panel_wrapped,
    validate_layout_wrapped,
    make_share_token_wrapped,
    render_snapshot_wrapped,
    make_dashboard_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_dashboard_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the C2 agent."""
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
        tools=DASHBOARD_COMPOSER_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR C2")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the C2 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING C2 RESULTS")
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


class DashboardComposerAgent(BaseAgent):
    """OO wrapper for the C2 agent (node type ``dashboard.compose``)."""

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
        return make_dashboard_agent(**self._params)

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
    "DashboardComposerAgent",
    "make_dashboard_agent",
    "DASHBOARD_COMPOSER_TOOLS",
]
