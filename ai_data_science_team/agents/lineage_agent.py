from __future__ import annotations

"""J12 Agent.

Phase-5 agent wrapper for spec J12.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.lineage``) with
LangChain ``@tool`` decorators and exposes the standard
``make_lineage_agent`` factory + ``J12Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``lineage.render``
"""

import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Dict,
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
from ai_data_science_team.tools.lineage import (  # noqa: E402, F401
    LineageGraph,
    add_edge,
    add_node,
    ancestors,
    descendants,
    node_summary,
    render_graph,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "lineage_agent"
NODE_TYPE = "lineage.render"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def add_node_wrapped(graph: LineageGraph) -> Tuple[str, dict]:
    """Tool wrapper for ``add_node``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j12_add_node")
    kwargs = {"graph": graph}
    try:
        result = add_node(**kwargs)
    except Exception as exc:
        return f"Tool j12_add_node failed: {exc}", {
            "add_node": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j12_add_node: ok"
    return content, {
        "add_node": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def add_edge_wrapped(
    graph: LineageGraph, source: str, target: str, relation: str
) -> Tuple[str, dict]:
    """Tool wrapper for ``add_edge``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j12_add_edge")
    kwargs = {"graph": graph, "source": source, "target": target, "relation": relation}
    try:
        result = add_edge(**kwargs)
    except Exception as exc:
        return f"Tool j12_add_edge failed: {exc}", {
            "add_edge": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j12_add_edge: ok"
    return content, {
        "add_edge": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def ancestors_wrapped(graph: LineageGraph, node_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``ancestors``.

    All upstream node_ids via BFS over incoming edges.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j12_ancestors")
    kwargs = {"graph": graph, "node_id": node_id}
    try:
        result = ancestors(**kwargs)
    except Exception as exc:
        return f"Tool j12_ancestors failed: {exc}", {
            "ancestors": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j12_ancestors: ok"
    return content, {
        "ancestors": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def descendants_wrapped(graph: LineageGraph, node_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``descendants``.

    All downstream node_ids via BFS over outgoing edges.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j12_descendants")
    kwargs = {"graph": graph, "node_id": node_id}
    try:
        result = descendants(**kwargs)
    except Exception as exc:
        return f"Tool j12_descendants failed: {exc}", {
            "descendants": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j12_descendants: ok"
    return content, {
        "descendants": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def render_graph_wrapped(graph: LineageGraph) -> Tuple[str, dict]:
    """Tool wrapper for ``render_graph``.

    Build a UI-ready dict. mode='impact' highlights all

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j12_render_graph")
    kwargs = {"graph": graph}
    try:
        result = render_graph(**kwargs)
    except Exception as exc:
        return f"Tool j12_render_graph failed: {exc}", {
            "render_graph": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j12_render_graph: ok"
    return content, {
        "render_graph": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def node_summary_wrapped(graph: LineageGraph, node_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``node_summary``.

    Return a single node + ancestors + descendants summary.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j12_node_summary")
    kwargs = {"graph": graph, "node_id": node_id}
    try:
        result = node_summary(**kwargs)
    except Exception as exc:
        return f"Tool j12_node_summary failed: {exc}", {
            "node_summary": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j12_node_summary: ok"
    return content, {
        "node_summary": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


LINEAGE_TOOLS = [
    add_node_wrapped,
    add_edge_wrapped,
    ancestors_wrapped,
    descendants_wrapped,
    render_graph_wrapped,
    node_summary_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_lineage_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J12 agent."""
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
        tools=LINEAGE_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR J12")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the J12 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING J12 RESULTS")
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


class LineageGraphAgent(BaseAgent):
    """OO wrapper for the J12 agent (node type ``lineage.render``)."""

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
        return make_lineage_agent(**self._params)

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
    "LineageGraphAgent",
    "make_lineage_agent",
    "LINEAGE_TOOLS",
]
