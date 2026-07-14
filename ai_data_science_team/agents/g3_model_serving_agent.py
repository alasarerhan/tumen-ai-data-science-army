"""G3 Agent.

Phase-5 agent wrapper for spec G3.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.g3_model_serving``) with
LangChain ``@tool`` decorators and exposes the standard
``make_g3_model_serving_agent`` factory + ``G3Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``deploy.serve``
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

from typing import Dict, Optional, Iterable

from ai_data_science_team.tools.g3_model_serving import (
    DeploymentRecord,
    PORT_POOL,
    RollbackRecord,
    allocate_port,
    record_deployment,
    record_rollback,
    render_bentofile,
    render_dockerfile,
    render_fastapi_app,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "g3_agent"
NODE_TYPE = "deploy.serve"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def g3_allocate_port_wrapped(used_ports: Optional[Iterable[int]]) -> Tuple[str, dict]:
    """Tool wrapper for ``allocate_port``.

    Return the first free port in PORT_POOL.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g3_allocate_port")
    kwargs = {'used_ports': used_ports}
    try:
        result = allocate_port(**kwargs)
    except Exception as exc:
        return f"Tool g3_allocate_port failed: {exc}", {
            "g3_allocate_port": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g3_allocate_port: ok"
    return content, {
        "g3_allocate_port": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g3_render_dockerfile_wrapped(model_id: str, version: str) -> Tuple[str, dict]:
    """Tool wrapper for ``render_dockerfile``.

    Return a Dockerfile body for serving ``model_id`` v``version``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g3_render_dockerfile")
    kwargs = {'model_id': model_id, 'version': version}
    try:
        result = render_dockerfile(**kwargs)
    except Exception as exc:
        return f"Tool g3_render_dockerfile failed: {exc}", {
            "g3_render_dockerfile": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g3_render_dockerfile: ok"
    return content, {
        "g3_render_dockerfile": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g3_render_bentofile_wrapped(model_id: str, version: str) -> Tuple[str, dict]:
    """Tool wrapper for ``render_bentofile``.

    Return a bentofile.yaml body for serving ``model_id`` v``version``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g3_render_bentofile")
    kwargs = {'model_id': model_id, 'version': version}
    try:
        result = render_bentofile(**kwargs)
    except Exception as exc:
        return f"Tool g3_render_bentofile failed: {exc}", {
            "g3_render_bentofile": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g3_render_bentofile: ok"
    return content, {
        "g3_render_bentofile": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g3_render_fastapi_app_wrapped(model_id: str, version: str) -> Tuple[str, dict]:
    """Tool wrapper for ``render_fastapi_app``.

    Return a FastAPI ``app/main.py`` body.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g3_render_fastapi_app")
    kwargs = {'model_id': model_id, 'version': version}
    try:
        result = render_fastapi_app(**kwargs)
    except Exception as exc:
        return f"Tool g3_render_fastapi_app failed: {exc}", {
            "g3_render_fastapi_app": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g3_render_fastapi_app: ok"
    return content, {
        "g3_render_fastapi_app": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g3_record_deployment_wrapped(model_id: str, version: str, target: str) -> Tuple[str, dict]:
    """Tool wrapper for ``record_deployment``.

    Build a deployment record (used by the workflow runtime).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g3_record_deployment")
    kwargs = {'model_id': model_id, 'version': version, 'target': target}
    try:
        result = record_deployment(**kwargs)
    except Exception as exc:
        return f"Tool g3_record_deployment failed: {exc}", {
            "g3_record_deployment": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g3_record_deployment: ok"
    return content, {
        "g3_record_deployment": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def g3_record_rollback_wrapped(deployment_id: str, from_version: str, to_version: str) -> Tuple[str, dict]:
    """Tool wrapper for ``record_rollback``.

    Build a rollback record.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: g3_record_rollback")
    kwargs = {'deployment_id': deployment_id, 'from_version': from_version, 'to_version': to_version}
    try:
        result = record_rollback(**kwargs)
    except Exception as exc:
        return f"Tool g3_record_rollback failed: {exc}", {
            "g3_record_rollback": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "g3_record_rollback: ok"
    return content, {
        "g3_record_rollback": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


G3_TOOLS = [
    g3_allocate_port_wrapped,
    g3_render_dockerfile_wrapped,
    g3_render_bentofile_wrapped,
    g3_render_fastapi_app_wrapped,
    g3_record_deployment_wrapped,
    g3_record_rollback_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_g3_model_serving_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the G3 agent."""
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
        tools=G3_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR G3")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the G3 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING G3 RESULTS")
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


class G3Agent(BaseAgent):
    """OO wrapper for the G3 agent (node type ``deploy.serve``)."""

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
        return make_g3_model_serving_agent(**self._params)

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
    "G3Agent",
    "make_g3_model_serving_agent",
    "G3_TOOLS",
]
