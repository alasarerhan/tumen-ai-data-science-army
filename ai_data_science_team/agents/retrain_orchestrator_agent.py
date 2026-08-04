from __future__ import annotations

"""G2 Agent.

Phase-5 agent wrapper for spec G2.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.retrain_orchestrator``) with
LangChain ``@tool`` decorators and exposes the standard
``make_retrain_orchestrator_agent`` factory + ``G2Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``monitor.retrain``
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
from ai_data_science_team.tools.retrain_orchestrator import (  # noqa: E402, F401
    Event,
    Policy,
    build_audit_trail,
    build_policy,
    decide_action,
    event_to_dict,
    record_event,
    simulate,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "retrain_orchestrator_agent"
NODE_TYPE = "monitor.retrain"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def build_policy_wrapped(spec: Mapping[str, Any]) -> Tuple[str, dict]:
    """Tool wrapper for ``build_policy``.

    Construct a Policy from a declarative spec dict.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g2_build_policy")
    kwargs = {"spec": spec}
    try:
        result = build_policy(**kwargs)
    except Exception as exc:
        return f"Tool g2_build_policy failed: {exc}", {
            "build_policy": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g2_build_policy: ok"
    return content, {
        "build_policy": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def decide_action_wrapped(signal: Mapping[str, Any], policy: Policy) -> Tuple[str, dict]:
    """Tool wrapper for ``decide_action``.

    Decide whether to trigger retraining for ``signal`` under ``policy``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g2_decide_action")
    kwargs = {"signal": signal, "policy": policy}
    try:
        result = decide_action(**kwargs)
    except Exception as exc:
        return f"Tool g2_decide_action failed: {exc}", {
            "decide_action": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g2_decide_action: ok"
    return content, {
        "decide_action": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def simulate_wrapped(signals: Sequence[Mapping[str, Any]], policy: Policy) -> Tuple[str, dict]:
    """Tool wrapper for ``simulate``.

    Replay ``signals`` against ``policy`` and count triggers.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g2_simulate")
    kwargs = {"signals": signals, "policy": policy}
    try:
        result = simulate(**kwargs)
    except Exception as exc:
        return f"Tool g2_simulate failed: {exc}", {
            "simulate": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g2_simulate: ok"
    return content, {
        "simulate": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def record_event_wrapped(
    policy: Policy, signal: Dict[str, Any], decision: Dict[str, Any]
) -> Tuple[str, dict]:
    """Tool wrapper for ``record_event``.

    Record a single audit-trail event.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g2_record_event")
    kwargs = {"policy": policy, "signal": signal, "decision": decision}
    try:
        result = record_event(**kwargs)
    except Exception as exc:
        return f"Tool g2_record_event failed: {exc}", {
            "record_event": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g2_record_event: ok"
    return content, {
        "record_event": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def event_to_dict_wrapped(ev: Event) -> Tuple[str, dict]:
    """Tool wrapper for ``event_to_dict``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g2_event_to_dict")
    kwargs = {"ev": ev}
    try:
        result = event_to_dict(**kwargs)
    except Exception as exc:
        return f"Tool g2_event_to_dict failed: {exc}", {
            "event_to_dict": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g2_event_to_dict: ok"
    return content, {
        "event_to_dict": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def build_audit_trail_wrapped(events: Sequence[Event]) -> Tuple[str, dict]:
    """Tool wrapper for ``build_audit_trail``.

    Convert a list of events into a chronologically-sorted audit trail.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g2_build_audit_trail")
    kwargs = {"events": events}
    try:
        result = build_audit_trail(**kwargs)
    except Exception as exc:
        return f"Tool g2_build_audit_trail failed: {exc}", {
            "build_audit_trail": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g2_build_audit_trail: ok"
    return content, {
        "build_audit_trail": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


RETRAIN_ORCHESTRATOR_TOOLS = [
    build_policy_wrapped,
    decide_action_wrapped,
    simulate_wrapped,
    record_event_wrapped,
    event_to_dict_wrapped,
    build_audit_trail_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_retrain_orchestrator_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the G2 agent."""
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
        tools=RETRAIN_ORCHESTRATOR_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR G2")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the G2 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING G2 RESULTS")
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


class RetrainOrchestratorAgent(BaseAgent):
    """OO wrapper for the G2 agent (node type ``monitor.retrain``)."""

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
        return make_retrain_orchestrator_agent(**self._params)

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
    "RetrainOrchestratorAgent",
    "make_retrain_orchestrator_agent",
    "RETRAIN_ORCHESTRATOR_TOOLS",
]
