"""I2 Agent.

Phase-5 agent wrapper for spec I2.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.i2_catalog``) with
LangChain ``@tool`` decorators and exposes the standard
``make_i2_catalog_agent`` factory + ``I2Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``catalog.search``
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

from typing import List, Dict, Optional, Sequence, Mapping

from ai_data_science_team.tools.i2_catalog import (
    Catalog,
    ColumnEntry,
    DEFAULT_SYNONYMS,
    I2_CATALOG_TOOL_NAMES,
    SearchHit,
    SourceEntry,
    TableEntry,
    add_pii_badges,
    add_source,
    add_table,
    add_term,
    attach_profile,
    bind_term_column,
    catalog_tree,
    lineage_for,
    make_catalog,
    record_lineage,
    resolve_data,
    search,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "i2_agent"
NODE_TYPE = "catalog.search"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def i2_add_source_wrapped(catalog: Catalog) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": SourceEntry,
    "content": str,
}]:
    """Tool wrapper for ``add_source``.

    Register a new source and return the entry.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_add_source")
    kwargs = {'catalog': catalog}
    try:
        result = add_source(**kwargs)
    except Exception as exc:
        return f"Tool i2_add_source failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_add_source: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_add_table_wrapped(catalog: Catalog, source_name: str, table_name: str, columns: Sequence[Mapping[str, Any]], description: Optional[str]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Optional[TableEntry],
    "content": str,
}]:
    """Tool wrapper for ``add_table``.

    Append a new table to an existing source.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_add_table")
    kwargs = {'catalog': catalog, 'source_name': source_name, 'table_name': table_name, 'columns': columns, 'description': description}
    try:
        result = add_table(**kwargs)
    except Exception as exc:
        return f"Tool i2_add_table failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_add_table: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_attach_profile_wrapped(catalog: Catalog, source_name: str, profile: Mapping[str, Any]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": None,
    "content": str,
}]:
    """Tool wrapper for ``attach_profile``.

    Fold a ``profile_dataframe`` (B1) result onto ``source_name``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_attach_profile")
    kwargs = {'catalog': catalog, 'source_name': source_name, 'profile': profile}
    try:
        result = attach_profile(**kwargs)
    except Exception as exc:
        return f"Tool i2_attach_profile failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_attach_profile: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_add_pii_badges_wrapped(catalog: Catalog, source_name: str, pii_scan: Mapping[str, Any]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": None,
    "content": str,
}]:
    """Tool wrapper for ``add_pii_badges``.

    Fold a ``scan_pii`` (B5) result onto ``source_name``.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_add_pii_badges")
    kwargs = {'catalog': catalog, 'source_name': source_name, 'pii_scan': pii_scan}
    try:
        result = add_pii_badges(**kwargs)
    except Exception as exc:
        return f"Tool i2_add_pii_badges failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_add_pii_badges: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_catalog_tree_wrapped(catalog: Catalog) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Dict[str, Any],
    "content": str,
}]:
    """Tool wrapper for ``catalog_tree``.

    Return the source → table → column tree for the I2 UI.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_catalog_tree")
    kwargs = {'catalog': catalog}
    try:
        result = catalog_tree(**kwargs)
    except Exception as exc:
        return f"Tool i2_catalog_tree failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_catalog_tree: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_add_term_wrapped(catalog: Catalog, term: str) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": None,
    "content": str,
}]:
    """Tool wrapper for ``add_term``.

    Register a business term; optionally add synonyms.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_add_term")
    kwargs = {'catalog': catalog, 'term': term}
    try:
        result = add_term(**kwargs)
    except Exception as exc:
        return f"Tool i2_add_term failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_add_term: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_bind_term_column_wrapped(catalog: Catalog, term: str) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": bool,
    "content": str,
}]:
    """Tool wrapper for ``bind_term_column``.

    Link a term to a specific source.table.column.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_bind_term_column")
    kwargs = {'catalog': catalog, 'term': term}
    try:
        result = bind_term_column(**kwargs)
    except Exception as exc:
        return f"Tool i2_bind_term_column failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_bind_term_column: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_search_wrapped(catalog: Catalog, query: str) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": List[SearchHit],
    "content": str,
}]:
    """Tool wrapper for ``search``.

    Search columns by query (term/description).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_search")
    kwargs = {'catalog': catalog, 'query': query}
    try:
        result = search(**kwargs)
    except Exception as exc:
        return f"Tool i2_search failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_search: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_resolve_data_wrapped(catalog: Catalog, term: str) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": List[Dict[str, Any]],
    "content": str,
}]:
    """Tool wrapper for ``resolve_data``.

    I1 planner entrypoint: NL term → top source.column candidates.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_resolve_data")
    kwargs = {'catalog': catalog, 'term': term}
    try:
        result = resolve_data(**kwargs)
    except Exception as exc:
        return f"Tool i2_resolve_data failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_resolve_data: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_record_lineage_wrapped(catalog: Catalog) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": None,
    "content": str,
}]:
    """Tool wrapper for ``record_lineage``.

    Append a record indicating that ``pipeline_id`` consumes

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_record_lineage")
    kwargs = {'catalog': catalog}
    try:
        result = record_lineage(**kwargs)
    except Exception as exc:
        return f"Tool i2_record_lineage failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_record_lineage: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_lineage_for_wrapped(catalog: Catalog, source_name: str, table: Optional[str]) -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": List[Dict[str, str]],
    "content": str,
}]:
    """Tool wrapper for ``lineage_for``.

    Return all lineage records that consume the given source (and table).

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_lineage_for")
    kwargs = {'catalog': catalog, 'source_name': source_name, 'table': table}
    try:
        result = lineage_for(**kwargs)
    except Exception as exc:
        return f"Tool i2_lineage_for failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_lineage_for: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def i2_make_catalog_wrapped() -> Tuple[str, {
    "name": str,
    "args": dict,
    "result": Catalog,
    "content": str,
}]:
    """Tool wrapper for ``make_catalog``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: i2_make_catalog")
    kwargs = {}
    try:
        result = make_catalog(**kwargs)
    except Exception as exc:
        return f"Tool i2_make_catalog failed: {exc}", {
            "name": name, "args": kwargs, "result": None, "content": f"error: {exc}"
        }
    content = f"i2_make_catalog: ok"
    return content, {
        "name": name,
        "args": kwargs,
        "result": result,
        "content": content,
    }



I2_TOOLS = [
    i2_add_source_wrapped,
    i2_add_table_wrapped,
    i2_attach_profile_wrapped,
    i2_add_pii_badges_wrapped,
    i2_catalog_tree_wrapped,
    i2_add_term_wrapped,
    i2_bind_term_column_wrapped,
    i2_search_wrapped,
    i2_resolve_data_wrapped,
    i2_record_lineage_wrapped,
    i2_lineage_for_wrapped,
    i2_make_catalog_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_i2_catalog_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the I2 agent."""
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
        tools=I2_TOOLS,
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
        messages = [("system", "You are the I2 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info(f"    * POST-PROCESSING I2 RESULTS")
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


class I2Agent(BaseAgent):
    """OO wrapper for the I2 agent (node type ``catalog.search``)."""

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
        return make_i2_catalog_agent(**self._params)

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
    "I2Agent",
    "make_i2_catalog_agent",
    "I2_TOOLS",
]
