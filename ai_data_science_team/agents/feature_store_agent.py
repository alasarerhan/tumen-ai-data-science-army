from __future__ import annotations

"""D3 Agent.

Phase-5 agent wrapper for spec D3.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.feature_store``) with
LangChain ``@tool`` decorators and exposes the standard
``make_feature_store_agent`` factory + ``D3Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``feature.register``
"""

from typing import (Dict, Optional, Tuple)  # noqa: E402
import logging  # noqa: E402, F401
from typing import Any  # noqa: E402, F401

from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, Sequence, TypedDict  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401



from ai_data_science_team.tools.feature_store import (  # noqa: E402, F401
    FeatureStore,
    FreshnessRecord,
    attach_lineage,
    bulk_probe_freshness,
    catalog_payload,
    check_consistency,
    latest_version,
    probe_freshness,
    register_feature,
    search_features,
    version_sort_key,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "feature_store_agent"
NODE_TYPE = "feature.register"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def register_feature_wrapped(store: FeatureStore) -> Tuple[str, dict]:
    """Tool wrapper for ``register_feature``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_register_feature")
    kwargs = {'store': store}
    try:
        result = register_feature(**kwargs)
    except Exception as exc:
        return f"Tool d3_register_feature failed: {exc}", {
            "register_feature": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_register_feature: ok"
    return content, {
        "register_feature": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def search_features_wrapped(store: FeatureStore) -> Tuple[str, dict]:
    """Tool wrapper for ``search_features``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_search_features")
    kwargs = {'store': store}
    try:
        result = search_features(**kwargs)
    except Exception as exc:
        return f"Tool d3_search_features failed: {exc}", {
            "search_features": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_search_features: ok"
    return content, {
        "search_features": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def version_sort_key_wrapped(version: str) -> Tuple[str, dict]:
    """Tool wrapper for ``version_sort_key``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_version_sort_key")
    kwargs = {'version': version}
    try:
        result = version_sort_key(**kwargs)
    except Exception as exc:
        return f"Tool d3_version_sort_key failed: {exc}", {
            "version_sort_key": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_version_sort_key: ok"
    return content, {
        "version_sort_key": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def latest_version_wrapped(store: FeatureStore, name: str) -> Tuple[str, dict]:
    """Tool wrapper for ``latest_version``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_latest_version")
    kwargs = {'store': store, 'name': name}
    try:
        result = latest_version(**kwargs)
    except Exception as exc:
        return f"Tool d3_latest_version failed: {exc}", {
            "latest_version": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_latest_version: ok"
    return content, {
        "latest_version": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def check_consistency_wrapped() -> Tuple[str, dict]:
    """Tool wrapper for ``check_consistency``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_check_consistency")
    kwargs = {}
    try:
        result = check_consistency(**kwargs)
    except Exception as exc:
        return f"Tool d3_check_consistency failed: {exc}", {
            "check_consistency": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_check_consistency: ok"
    return content, {
        "check_consistency": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def probe_freshness_wrapped(record: FreshnessRecord) -> Tuple[str, dict]:
    """Tool wrapper for ``probe_freshness``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_probe_freshness")
    kwargs = {'record': record}
    try:
        result = probe_freshness(**kwargs)
    except Exception as exc:
        return f"Tool d3_probe_freshness failed: {exc}", {
            "probe_freshness": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_probe_freshness: ok"
    return content, {
        "probe_freshness": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def bulk_probe_freshness_wrapped(records: Sequence[FreshnessRecord]) -> Tuple[str, dict]:
    """Tool wrapper for ``bulk_probe_freshness``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_bulk_probe_freshness")
    kwargs = {'records': records}
    try:
        result = bulk_probe_freshness(**kwargs)
    except Exception as exc:
        return f"Tool d3_bulk_probe_freshness failed: {exc}", {
            "bulk_probe_freshness": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_bulk_probe_freshness: ok"
    return content, {
        "bulk_probe_freshness": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def attach_lineage_wrapped(store: FeatureStore) -> Tuple[str, dict]:
    """Tool wrapper for ``attach_lineage``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_attach_lineage")
    kwargs = {'store': store}
    try:
        result = attach_lineage(**kwargs)
    except Exception as exc:
        return f"Tool d3_attach_lineage failed: {exc}", {
            "attach_lineage": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_attach_lineage: ok"
    return content, {
        "attach_lineage": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def catalog_payload_wrapped(store: FeatureStore, feature_ids: Sequence[str]) -> Tuple[str, dict]:
    """Tool wrapper for ``catalog_payload``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: d3_catalog_payload")
    kwargs = {'store': store, 'feature_ids': feature_ids}
    try:
        result = catalog_payload(**kwargs)
    except Exception as exc:
        return f"Tool d3_catalog_payload failed: {exc}", {
            "catalog_payload": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "d3_catalog_payload: ok"
    return content, {
        "catalog_payload": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


FEATURE_STORE_TOOLS = [
    register_feature_wrapped,
    search_features_wrapped,
    version_sort_key_wrapped,
    latest_version_wrapped,
    check_consistency_wrapped,
    probe_freshness_wrapped,
    bulk_probe_freshness_wrapped,
    attach_lineage_wrapped,
    catalog_payload_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_feature_store_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the D3 agent."""
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
        tools=FEATURE_STORE_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR D3")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the D3 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING D3 RESULTS")
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


class FeatureStoreAgent(BaseAgent):
    """OO wrapper for the D3 agent (node type ``feature.register``)."""

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
        return make_feature_store_agent(**self._params)

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
    "FeatureStoreAgent",
    "make_feature_store_agent",
    "FEATURE_STORE_TOOLS",
]
