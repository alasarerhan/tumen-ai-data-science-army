"""B7 Agent.

Phase-5 agent wrapper for spec B7.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.b7_data_ingestion``) with
LangChain ``@tool`` decorators and exposes the standard
``make_b7_data_ingestion_agent`` factory + ``B7Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``data.ingest``
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

import pandas as pd
from typing import Dict, Any

from ai_data_science_team.tools.b7_data_ingestion import (
    B7_INGEST_TOOL_NAMES,
    IngestJob,
    RunRow,
    WatermarkState,
    compute_watermark,
    incremental_diff,
    record_run,
    register_ingest_job,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "b7_agent"
NODE_TYPE = "data.ingest"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def b7_register_ingest_job_wrapped(name: str, source: str, target: str) -> Tuple[str, dict]:
    """Tool wrapper for ``register_ingest_job``.

    Materialise an ingest-job record for the workflow registry.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b7_register_ingest_job")
    kwargs = {'name': name, 'source': source, 'target': target}
    try:
        result = register_ingest_job(**kwargs)
    except Exception as exc:
        return f"Tool b7_register_ingest_job failed: {exc}", {
            "b7_register_ingest_job": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"b7_register_ingest_job: ok"
    return content, {
        "b7_register_ingest_job": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def b7_compute_watermark_wrapped(job_id: str, previous: Any, current: Any) -> Tuple[str, dict]:
    """Tool wrapper for ``compute_watermark``.

    Return a watermark-progress record.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b7_compute_watermark")
    kwargs = {'job_id': job_id, 'previous': previous, 'current': current}
    try:
        result = compute_watermark(**kwargs)
    except Exception as exc:
        return f"Tool b7_compute_watermark failed: {exc}", {
            "b7_compute_watermark": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"b7_compute_watermark: ok"
    return content, {
        "b7_compute_watermark": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def b7_incremental_diff_wrapped(baseline: pd.DataFrame, current: pd.DataFrame) -> Tuple[str, dict]:
    """Tool wrapper for ``incremental_diff``.

    Diff two DataFrames for watermark-style incremental loads.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b7_incremental_diff")
    kwargs = {'baseline': baseline, 'current': current}
    try:
        result = incremental_diff(**kwargs)
    except Exception as exc:
        return f"Tool b7_incremental_diff failed: {exc}", {
            "b7_incremental_diff": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"b7_incremental_diff: ok"
    return content, {
        "b7_incremental_diff": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def b7_record_run_wrapped(job_id: str, run_id: str, status: str, started_at: str) -> Tuple[str, dict]:
    """Tool wrapper for ``record_run``.

    Build a single run-history row.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: b7_record_run")
    kwargs = {'job_id': job_id, 'run_id': run_id, 'status': status, 'started_at': started_at}
    try:
        result = record_run(**kwargs)
    except Exception as exc:
        return f"Tool b7_record_run failed: {exc}", {
            "b7_record_run": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = f"b7_record_run: ok"
    return content, {
        "b7_record_run": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }



B7_TOOLS = [
    b7_register_ingest_job_wrapped,
    b7_compute_watermark_wrapped,
    b7_incremental_diff_wrapped,
    b7_record_run_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_b7_data_ingestion_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the B7 agent."""
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
        tools=B7_TOOLS,
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
        logger.info(f"    * RUN REACT AGENT FOR B7")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the B7 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING B7 RESULTS")
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


class B7Agent(BaseAgent):
    """OO wrapper for the B7 agent (node type ``data.ingest``)."""

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
        return make_b7_data_ingestion_agent(**self._params)

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
    "B7Agent",
    "make_b7_data_ingestion_agent",
    "B7_TOOLS",
]
