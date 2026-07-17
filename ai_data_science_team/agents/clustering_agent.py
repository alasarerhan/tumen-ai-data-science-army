from __future__ import annotations

"""E12 Agent.

Phase-5 agent wrapper for spec E12.  Wraps the deterministic
tool layer (``ai_data_science_team.tools.clustering``) with
LangChain ``@tool`` decorators and exposes the standard
``make_clustering_agent`` factory + ``E12Agent`` OO
wrapper, following the same pattern as ABTestingAgent and
PowerAnalysisAgent.

Node type: ``model.train.cluster``
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

import numpy as np  # noqa: E402, F401
from typing import Mapping  # noqa: E402

from ai_data_science_team.tools.e12_clustering import (  # noqa: E402, F401
    ClusteringResult,
    build_naming_seeds,
    cluster_sizes,
    compute_calinski_harabasz,
    compute_silhouette,
    profile_clusters,
    result_payload,
    run_clustering,
    run_dbscan,
    run_hierarchical,
    run_kmeans,
    segmentation_template,
)


logger = logging.getLogger(__name__)

AGENT_NAME = "clustering_agent"
NODE_TYPE = "model.train.cluster"


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def run_kmeans_wrapped(X: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``run_kmeans``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_run_kmeans")
    kwargs = {'X': X}
    try:
        result = run_kmeans(**kwargs)
    except Exception as exc:
        return f"Tool e12_run_kmeans failed: {exc}", {
            "run_kmeans": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_run_kmeans: ok"
    return content, {
        "run_kmeans": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def run_dbscan_wrapped(X: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``run_dbscan``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_run_dbscan")
    kwargs = {'X': X}
    try:
        result = run_dbscan(**kwargs)
    except Exception as exc:
        return f"Tool e12_run_dbscan failed: {exc}", {
            "run_dbscan": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_run_dbscan: ok"
    return content, {
        "run_dbscan": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def run_hierarchical_wrapped(X: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``run_hierarchical``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_run_hierarchical")
    kwargs = {'X': X}
    try:
        result = run_hierarchical(**kwargs)
    except Exception as exc:
        return f"Tool e12_run_hierarchical failed: {exc}", {
            "run_hierarchical": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_run_hierarchical: ok"
    return content, {
        "run_hierarchical": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def compute_silhouette_wrapped(X: np.ndarray, labels: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``compute_silhouette``.

    Return silhouette score in [-1, 1]. Returns NaN if < 2 clusters

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_compute_silhouette")
    kwargs = {'X': X, 'labels': labels}
    try:
        result = compute_silhouette(**kwargs)
    except Exception as exc:
        return f"Tool e12_compute_silhouette failed: {exc}", {
            "compute_silhouette": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_compute_silhouette: ok"
    return content, {
        "compute_silhouette": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def compute_calinski_harabasz_wrapped(X: np.ndarray, labels: np.ndarray) -> Tuple[str, dict]:
    """Tool wrapper for ``compute_calinski_harabasz``.

    Return CH score. NaN if fewer than 2 clusters.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_compute_calinski_harabasz")
    kwargs = {'X': X, 'labels': labels}
    try:
        result = compute_calinski_harabasz(**kwargs)
    except Exception as exc:
        return f"Tool e12_compute_calinski_harabasz failed: {exc}", {
            "compute_calinski_harabasz": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_compute_calinski_harabasz: ok"
    return content, {
        "compute_calinski_harabasz": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def cluster_sizes_wrapped(labels: Sequence[int]) -> Tuple[str, dict]:
    """Tool wrapper for ``cluster_sizes``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_cluster_sizes")
    kwargs = {'labels': labels}
    try:
        result = cluster_sizes(**kwargs)
    except Exception as exc:
        return f"Tool e12_cluster_sizes failed: {exc}", {
            "cluster_sizes": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_cluster_sizes: ok"
    return content, {
        "cluster_sizes": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def profile_clusters_wrapped(X: np.ndarray, labels: Sequence[int], feature_names: Optional[Sequence[str]]) -> Tuple[str, dict]:
    """Tool wrapper for ``profile_clusters``.

    Per-cluster mean / std / min / max for each feature.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_profile_clusters")
    kwargs = {'X': X, 'labels': labels, 'feature_names': feature_names}
    try:
        result = profile_clusters(**kwargs)
    except Exception as exc:
        return f"Tool e12_profile_clusters failed: {exc}", {
            "profile_clusters": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_profile_clusters: ok"
    return content, {
        "profile_clusters": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def build_naming_seeds_wrapped(profiles: Sequence[Mapping[str, Any]]) -> Tuple[str, dict]:
    """Tool wrapper for ``build_naming_seeds``.

    Build deterministic naming seeds per cluster. Each entry

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_build_naming_seeds")
    kwargs = {'profiles': profiles}
    try:
        result = build_naming_seeds(**kwargs)
    except Exception as exc:
        return f"Tool e12_build_naming_seeds failed: {exc}", {
            "build_naming_seeds": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_build_naming_seeds: ok"
    return content, {
        "build_naming_seeds": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def segmentation_template_wrapped(profiles: Sequence[Mapping[str, Any]], naming_seeds: Sequence[Mapping[str, Any]]) -> Tuple[str, dict]:
    """Tool wrapper for ``segmentation_template``.

    Build a marketing-segment-style template: each cluster becomes

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_segmentation_template")
    kwargs = {'profiles': profiles, 'naming_seeds': naming_seeds}
    try:
        result = segmentation_template(**kwargs)
    except Exception as exc:
        return f"Tool e12_segmentation_template failed: {exc}", {
            "segmentation_template": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_segmentation_template: ok"
    return content, {
        "segmentation_template": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def run_clustering_wrapped(X: Any) -> Tuple[str, dict]:
    """Tool wrapper for ``run_clustering``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_run_clustering")
    kwargs = {'X': X}
    try:
        result = run_clustering(**kwargs)
    except Exception as exc:
        return f"Tool e12_run_clustering failed: {exc}", {
            "run_clustering": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_run_clustering: ok"
    return content, {
        "run_clustering": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


@tool(response_format="content_and_artifact")
def result_payload_wrapped(r: ClusteringResult) -> Tuple[str, dict]:
    """Tool wrapper for ``result_payload``.

    See underlying tool module.

    Returns a (content, artifact) tuple per the react-agent contract.
    """
    logger.info("    * Tool: e12_result_payload")
    kwargs = {'r': r}
    try:
        result = result_payload(**kwargs)
    except Exception as exc:
        return f"Tool e12_result_payload failed: {exc}", {
            "result_payload": kwargs,
            "args": kwargs,
            "result": None,
            "content": f"error: {exc}",
        }
    content = "e12_result_payload: ok"
    return content, {
        "result_payload": kwargs,
        "args": kwargs,
        "result": result,
        "content": content,
    }


CLUSTERING_TOOLS = [
    run_kmeans_wrapped,
    run_dbscan_wrapped,
    run_hierarchical_wrapped,
    compute_silhouette_wrapped,
    compute_calinski_harabasz_wrapped,
    cluster_sizes_wrapped,
    profile_clusters_wrapped,
    build_naming_seeds_wrapped,
    segmentation_template_wrapped,
    run_clustering_wrapped,
    result_payload_wrapped,
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_clustering_agent(
    model: Any,
    checkpointer: Optional[Checkpointer] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    log_tool_calls: bool = True,
):
    """Build the LangGraph StateGraph for the E12 agent."""
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
        tools=CLUSTERING_TOOLS,
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
        logger.info("    * RUN REACT AGENT FOR E12")
        base = state.get("messages") or [("user", state.get("user_instructions"))]
        messages = [("system", "You are the E12 agent. Use the available tools to complete the user's request.")] + list(base)
        input_payload = {"messages": messages}
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING E12 RESULTS")
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


class ClusteringAgent(BaseAgent):
    """OO wrapper for the E12 agent (node type ``model.train.cluster``)."""

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
        return make_clustering_agent(**self._params)

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
    "ClusteringAgent",
    "make_clustering_agent",
    "CLUSTERING_TOOLS",
]
