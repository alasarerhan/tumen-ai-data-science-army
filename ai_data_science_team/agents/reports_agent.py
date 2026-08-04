from __future__ import annotations

"""C5 Agent.

Phase-5 agent wrapper for spec C5.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.reports``) with
LangChain ``@tool`` decorators and exposes the standard
``make_reports_agent`` factory + ``C5Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``report.render``
"""

import logging  # noqa: E402, F401
from typing import (  # noqa: E402
    Any,  # noqa: E402, F401
    Dict,
    Mapping,  # noqa: E402, F401
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
from ai_data_science_team.tools.reports import (  # noqa: E402, F401
    build_report,
    compute_schedule,
    get_template,
    render_markdown,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "reports_agent"
NODE_TYPE = "report.render"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def get_template_wrapped(template_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``get_template``.

    Return the template dict for ``template_id``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c5_get_template")
    kwargs = {"template_id": template_id}
    try:
        result = get_template(**kwargs)
    except Exception as exc:
        return f"Tool c5_get_template failed: {exc}", {
            "get_template": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c5_get_template: ok"
    return content, {
        "get_template": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def build_report_wrapped(template_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``build_report``.

    Build a report dict for the given template id.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c5_build_report")
    kwargs = {"template_id": template_id}
    try:
        result = build_report(**kwargs)
    except Exception as exc:
        return f"Tool c5_build_report failed: {exc}", {
            "build_report": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c5_build_report: ok"
    return content, {
        "build_report": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def compute_schedule_wrapped(
    period: str, starting_at_epoch: float, n_runs: int
) -> Tuple[str, dict]:
    """Tool wrapper for ``compute_schedule``.

    Return the next ``n_runs`` schedule timestamps (epoch seconds).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c5_compute_schedule")
    kwargs = {"period": period, "starting_at_epoch": starting_at_epoch, "n_runs": n_runs}
    try:
        result = compute_schedule(**kwargs)
    except Exception as exc:
        return f"Tool c5_compute_schedule failed: {exc}", {
            "compute_schedule": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c5_compute_schedule: ok"
    return content, {
        "compute_schedule": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def render_markdown_wrapped(report: Mapping[str, Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``render_markdown``.

    Render a built report dict as a Markdown string.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: c5_render_markdown")
    kwargs = {"report": report}
    try:
        result = render_markdown(**kwargs)
    except Exception as exc:
        return f"Tool c5_render_markdown failed: {exc}", {
            "render_markdown": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "c5_render_markdown: ok"
    return content, {
        "render_markdown": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


REPORT_GENERATOR_TOOLS = [
    get_template_wrapped,
    build_report_wrapped,
    compute_schedule_wrapped,
    render_markdown_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_reports_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the C5 agent."""
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
        tools=REPORT_GENERATOR_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR C5")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the C5 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING C5 RESULTS")
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


class ReportGeneratorAgent(BaseAgent):
    """OO wrapper for the C5 agent (node type ``report.render``)."""

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
        return make_reports_agent(**self._params)

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
    "ReportGeneratorAgent",
    "make_reports_agent",
    "REPORT_GENERATOR_TOOLS",
]
