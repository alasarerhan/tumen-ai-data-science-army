from __future__ import annotations

"""G7 Agent.

Phase-5 agent wrapper for spec G7.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.alerting``) with
LangChain ``@tool`` decorators and exposes the standard
``make_alerting_agent`` factory + ``G7Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``incident.raise``
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
from ai_data_science_team.tools.alerting import (  # noqa: E402, F401
    AlertRule,
    AlertStore,
    Incident,
    IncidentStore,
    acknowledge_incident,
    channel_template,
    define_rule,
    evaluate_rule,
    raise_incident,
    resolve_incident,
    route_to_channels,
    summarise,
    tick_escalation,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "alerting_agent"
NODE_TYPE = "incident.raise"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def define_rule_wrapped(store: AlertStore) -> Tuple[str, dict]:
    """Tool wrapper for ``define_rule``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_define_rule")
    kwargs = {"store": store}
    try:
        result = define_rule(**kwargs)
    except Exception as exc:
        return f"Tool g7_define_rule failed: {exc}", {
            "define_rule": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_define_rule: ok"
    return content, {
        "define_rule": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def evaluate_rule_wrapped(rule: AlertRule) -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_rule``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_evaluate_rule")
    kwargs = {"rule": rule}
    try:
        result = evaluate_rule(**kwargs)
    except Exception as exc:
        return f"Tool g7_evaluate_rule failed: {exc}", {
            "evaluate_rule": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_evaluate_rule: ok"
    return content, {
        "evaluate_rule": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def raise_incident_wrapped(store: AlertStore) -> Tuple[str, dict]:
    """Tool wrapper for ``raise_incident``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_raise_incident")
    kwargs = {"store": store}
    try:
        result = raise_incident(**kwargs)
    except Exception as exc:
        return f"Tool g7_raise_incident failed: {exc}", {
            "raise_incident": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_raise_incident: ok"
    return content, {
        "raise_incident": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def acknowledge_incident_wrapped(inc: Incident) -> Tuple[str, dict]:
    """Tool wrapper for ``acknowledge_incident``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_acknowledge_incident")
    kwargs = {"inc": inc}
    try:
        result = acknowledge_incident(**kwargs)
    except Exception as exc:
        return f"Tool g7_acknowledge_incident failed: {exc}", {
            "acknowledge_incident": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_acknowledge_incident: ok"
    return content, {
        "acknowledge_incident": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def resolve_incident_wrapped(inc: Incident) -> Tuple[str, dict]:
    """Tool wrapper for ``resolve_incident``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_resolve_incident")
    kwargs = {"inc": inc}
    try:
        result = resolve_incident(**kwargs)
    except Exception as exc:
        return f"Tool g7_resolve_incident failed: {exc}", {
            "resolve_incident": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_resolve_incident: ok"
    return content, {
        "resolve_incident": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def tick_escalation_wrapped(inc: Incident) -> Tuple[str, dict]:
    """Tool wrapper for ``tick_escalation``.

    Walk the escalation chain. Trigger any step whose

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_tick_escalation")
    kwargs = {"inc": inc}
    try:
        result = tick_escalation(**kwargs)
    except Exception as exc:
        return f"Tool g7_tick_escalation failed: {exc}", {
            "tick_escalation": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_tick_escalation: ok"
    return content, {
        "tick_escalation": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def route_to_channels_wrapped(inc: Incident) -> Tuple[str, dict]:
    """Tool wrapper for ``route_to_channels``.

    Build a payload per channel. If send_fn is provided, also

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_route_to_channels")
    kwargs = {"inc": inc}
    try:
        result = route_to_channels(**kwargs)
    except Exception as exc:
        return f"Tool g7_route_to_channels failed: {exc}", {
            "route_to_channels": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_route_to_channels: ok"
    return content, {
        "route_to_channels": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def channel_template_wrapped(channel: str, payload: Mapping[str, Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``channel_template``.

    Render a human-readable message for a given channel.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_channel_template")
    kwargs = {"channel": channel, "payload": payload}
    try:
        result = channel_template(**kwargs)
    except Exception as exc:
        return f"Tool g7_channel_template failed: {exc}", {
            "channel_template": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_channel_template: ok"
    return content, {
        "channel_template": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def summarise_wrapped(store: IncidentStore) -> Tuple[str, dict]:
    """Tool wrapper for ``summarise``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_summarise")
    kwargs = {"store": store}
    try:
        result = summarise(**kwargs)
    except Exception as exc:
        return f"Tool g7_summarise failed: {exc}", {
            "summarise": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g7_summarise: ok"
    return content, {
        "summarise": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


ALERTING_TOOLS = [
    define_rule_wrapped,
    evaluate_rule_wrapped,
    raise_incident_wrapped,
    acknowledge_incident_wrapped,
    resolve_incident_wrapped,
    tick_escalation_wrapped,
    route_to_channels_wrapped,
    channel_template_wrapped,
    summarise_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_alerting_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the G7 agent."""
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
        tools=ALERTING_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR G7")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the G7 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING G7 RESULTS")
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


class AlertingAgent(BaseAgent):
    """OO wrapper for the G7 agent (node type ``incident.raise``)."""

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
        return make_alerting_agent(**self._params)

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
    "AlertingAgent",
    "make_alerting_agent",
    "ALERTING_TOOLS",
]
