"""G7 Agent.

Phase-5 agent wrapper for spec G7.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.g7_alerting``) with
LangChain ``@tool`` decorators and exposes the standard
``make_g7_alerting_agent`` factory + ``G7Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``incident.raise``
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

from typing import List, Dict, Mapping

from ai_data_science_team.tools.g7_alerting import (
    AlertRule,
    AlertStore,
    EscalationStep,
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


logger = logging.getLogger(__name__)

AGENT_NAME = "g7_agent"
NODE_TYPE = "incident.raise"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def g7_define_rule_wrapped(store: AlertStore) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": AlertRule,
    "content": str,
}]:
    """Tool wrapper for ``define_rule``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_define_rule")
    kwargs = {'store': store}
    try:
        result = define_rule(**kwargs)
    except Exception as exc:
        return f"Tool g7_define_rule failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_define_rule: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_evaluate_rule_wrapped(rule: AlertRule) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": bool,
    "content": str,
}]:
    """Tool wrapper for ``evaluate_rule``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_evaluate_rule")
    kwargs = {'rule': rule}
    try:
        result = evaluate_rule(**kwargs)
    except Exception as exc:
        return f"Tool g7_evaluate_rule failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_evaluate_rule: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_raise_incident_wrapped(store: AlertStore) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Incident,
    "content": str,
}]:
    """Tool wrapper for ``raise_incident``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_raise_incident")
    kwargs = {'store': store}
    try:
        result = raise_incident(**kwargs)
    except Exception as exc:
        return f"Tool g7_raise_incident failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_raise_incident: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_acknowledge_incident_wrapped(inc: Incident) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": None,
    "content": str,
}]:
    """Tool wrapper for ``acknowledge_incident``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_acknowledge_incident")
    kwargs = {'inc': inc}
    try:
        result = acknowledge_incident(**kwargs)
    except Exception as exc:
        return f"Tool g7_acknowledge_incident failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_acknowledge_incident: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_resolve_incident_wrapped(inc: Incident) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": None,
    "content": str,
}]:
    """Tool wrapper for ``resolve_incident``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_resolve_incident")
    kwargs = {'inc': inc}
    try:
        result = resolve_incident(**kwargs)
    except Exception as exc:
        return f"Tool g7_resolve_incident failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_resolve_incident: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_tick_escalation_wrapped(inc: Incident) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": List[EscalationStep],
    "content": str,
}]:
    """Tool wrapper for ``tick_escalation``.

    Walk the escalation chain. Trigger any step whose

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_tick_escalation")
    kwargs = {'inc': inc}
    try:
        result = tick_escalation(**kwargs)
    except Exception as exc:
        return f"Tool g7_tick_escalation failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_tick_escalation: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_route_to_channels_wrapped(inc: Incident) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, Any],
    "content": str,
}]:
    """Tool wrapper for ``route_to_channels``.

    Build a payload per channel. If send_fn is provided, also

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_route_to_channels")
    kwargs = {'inc': inc}
    try:
        result = route_to_channels(**kwargs)
    except Exception as exc:
        return f"Tool g7_route_to_channels failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_route_to_channels: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_channel_template_wrapped(channel: str, payload: Mapping[str, Any]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": str,
    "content": str,
}]:
    """Tool wrapper for ``channel_template``.

    Render a human-readable message for a given channel.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_channel_template")
    kwargs = {'channel': channel, 'payload': payload}
    try:
        result = channel_template(**kwargs)
    except Exception as exc:
        return f"Tool g7_channel_template failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_channel_template: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g7_summarise_wrapped(store: IncidentStore) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, int],
    "content": str,
}]:
    """Tool wrapper for ``summarise``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g7_summarise")
    kwargs = {'store': store}
    try:
        result = summarise(**kwargs)
    except Exception as exc:
        return f"Tool g7_summarise failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"g7_summarise: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }



G7_TOOLS = [
    g7_define_rule_wrapped,
    g7_evaluate_rule_wrapped,
    g7_raise_incident_wrapped,
    g7_acknowledge_incident_wrapped,
    g7_resolve_incident_wrapped,
    g7_tick_escalation_wrapped,
    g7_route_to_channels_wrapped,
    g7_channel_template_wrapped,
    g7_summarise_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_g7_alerting_agent(
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

    from langchain.agents import create_agent

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=G7_TOOLS,
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
        messages = [("system", "You are the G7 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING G7 RESULTS")
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


class G7Agent(BaseAgent):
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
        return make_g7_alerting_agent(**self._params)

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
    "G7Agent",
    "make_g7_alerting_agent",
    "G7_TOOLS",
]
