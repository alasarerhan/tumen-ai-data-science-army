from __future__ import annotations

"""J11 Agent.

Phase-5 agent wrapper for spec J11.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.shadow_canary``) with
LangChain ``@tool`` decorators and exposes the standard
``make_shadow_canary_agent`` factory + ``J11Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``deploy.shadow``
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
from ai_data_science_team.tools.shadow_canary import (  # noqa: E402, F401
    DeploymentStore,
    evaluate_rollback,
    list_deployments,
    mark_status,
    record_live_sample,
    start_deployment,
    summarise_deployment,
)
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

logger = logging.getLogger(__name__)

AGENT_NAME = "shadow_canary_agent"
NODE_TYPE = "deploy.shadow"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def start_deployment_wrapped(store: DeploymentStore) -> Tuple[str, dict]:
    """Tool wrapper for ``start_deployment``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j11_start_deployment")
    kwargs = {"store": store}
    try:
        result = start_deployment(**kwargs)
    except Exception as exc:
        return f"Tool j11_start_deployment failed: {exc}", {
            "start_deployment": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j11_start_deployment: ok"
    return content, {
        "start_deployment": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def record_live_sample_wrapped(store: DeploymentStore, deployment_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``record_live_sample``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j11_record_live_sample")
    kwargs = {"store": store, "deployment_id": deployment_id}
    try:
        result = record_live_sample(**kwargs)
    except Exception as exc:
        return f"Tool j11_record_live_sample failed: {exc}", {
            "record_live_sample": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j11_record_live_sample: ok"
    return content, {
        "record_live_sample": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def evaluate_rollback_wrapped(store: DeploymentStore, deployment_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``evaluate_rollback``.

    Evaluate auto-rollback thresholds for a deployment. Returns

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j11_evaluate_rollback")
    kwargs = {"store": store, "deployment_id": deployment_id}
    try:
        result = evaluate_rollback(**kwargs)
    except Exception as exc:
        return f"Tool j11_evaluate_rollback failed: {exc}", {
            "evaluate_rollback": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j11_evaluate_rollback: ok"
    return content, {
        "evaluate_rollback": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def mark_status_wrapped(
    store: DeploymentStore, deployment_id: str, status: str
) -> Tuple[str, dict]:
    """Tool wrapper for ``mark_status``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j11_mark_status")
    kwargs = {"store": store, "deployment_id": deployment_id, "status": status}
    try:
        result = mark_status(**kwargs)
    except Exception as exc:
        return f"Tool j11_mark_status failed: {exc}", {
            "mark_status": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j11_mark_status: ok"
    return content, {
        "mark_status": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def summarise_deployment_wrapped(store: DeploymentStore, deployment_id: str) -> Tuple[str, dict]:
    """Tool wrapper for ``summarise_deployment``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j11_summarise_deployment")
    kwargs = {"store": store, "deployment_id": deployment_id}
    try:
        result = summarise_deployment(**kwargs)
    except Exception as exc:
        return f"Tool j11_summarise_deployment failed: {exc}", {
            "summarise_deployment": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j11_summarise_deployment: ok"
    return content, {
        "summarise_deployment": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def list_deployments_wrapped(store: DeploymentStore) -> Tuple[str, dict]:
    """Tool wrapper for ``list_deployments``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: j11_list_deployments")
    kwargs = {"store": store}
    try:
        result = list_deployments(**kwargs)
    except Exception as exc:
        return f"Tool j11_list_deployments failed: {exc}", {
            "list_deployments": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "j11_list_deployments: ok"
    return content, {
        "list_deployments": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


SHADOW_CANARY_TOOLS = [
    start_deployment_wrapped,
    record_live_sample_wrapped,
    evaluate_rollback_wrapped,
    mark_status_wrapped,
    summarise_deployment_wrapped,
    list_deployments_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_shadow_canary_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the J11 agent."""
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
        tools=SHADOW_CANARY_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR J11")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [
            (
                "system",
                "You are the J11 agent. Use the available tools to complete the user's request.",
            )
        ] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING J11 RESULTS")
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


class ShadowCanaryAgent(BaseAgent):
    """OO wrapper for the J11 agent (node type ``deploy.shadow``)."""

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
        return make_shadow_canary_agent(**self._params)

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
    "ShadowCanaryAgent",
    "make_shadow_canary_agent",
    "SHADOW_CANARY_TOOLS",
]
