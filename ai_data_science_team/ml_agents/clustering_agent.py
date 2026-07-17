from __future__ import annotations

"""Clustering and Segmentation Agent — M14.

Provides ``ClusteringAgent``:
  - K-Means and DBSCAN clustering
  - PCA / t-SNE dimensionality reduction
  - Cluster profiling (per-cluster means / stds / sizes)
  - Silhouette-score quality assessment
  - Automatic interpretation and labelling of discovered segments

Building on ``BaseAgent`` (CompiledStateGraph subclass) with the standard
``prepare_messages → react_agent → post_process`` graph layout.

Example usage::

    from langchain_openai import ChatOpenAI  # noqa: E402, F401
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent  # noqa: E402, F401

    llm   = ChatOpenAI(model="gpt-4o-mini")
    agent = ClusteringAgent(model=llm)
    agent.invoke_agent(
        user_instructions=(
            "Müşteri verilerini segmentlere ayır, en iyi küme sayısını bul "
            "ve her segmenti yorumla."
        ),
        data=[[1.0, 2.0], [1.1, 2.1], [8.0, 8.5], [8.2, 8.3], [5.0, 5.0]],
        feature_names=["recency", "monetary"],
    )
    logger.info(agent.get_ai_message())
    logger.info(agent.get_artifacts())
"""
import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional, Sequence  # noqa: E402, F401

from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401
from typing_extensions import Annotated, TypedDict  # noqa: E402, F401

try:
    from IPython.display import Markdown  # optional — only needed in notebook contexts  # noqa: E402, F401
except ImportError:
    Markdown = None  # type: ignore[assignment,misc]

from langchain.agents import create_agent  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.tools.e12_clustering import (  # noqa: E402, F401
    run_kmeans,
    run_dbscan,
    reduce_pca,
    reduce_tsne,
    compute_cluster_profile,
    compute_silhouette,
)
from ai_data_science_team.utils.messages import get_tool_call_names  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Tools exposed to the agent
# ---------------------------------------------------------------------------

_CLUSTERING_TOOLS = [
    run_kmeans,
    run_dbscan,
    reduce_pca,
    reduce_tsne,
    compute_cluster_profile,
    compute_silhouette,
]

# ---------------------------------------------------------------------------
# Default system prompt
# ---------------------------------------------------------------------------

_CLUSTERING_SYSTEM_PROMPT = """You are an expert data scientist specialising in
clustering and customer segmentation.  You have access to the following tools:

- **run_kmeans**             – Fit K-Means; receives data matrix and n_clusters.
- **run_dbscan**             – Fit DBSCAN for density-based, arbitrary-shape clusters.
- **reduce_pca**             – PCA dimensionality reduction (use before t-SNE or as a
                               standalone step to understand feature importance).
- **reduce_tsne**            – t-SNE 2-D / 3-D embedding (use for visualisation).
- **compute_cluster_profile** – Per-cluster mean / std / size statistics.
- **compute_silhouette**     – Silhouette quality score (−1 to +1; higher = better).

**Recommended workflow:**
1. If the feature count is high (> 10), apply `reduce_pca` first.
2. Try `run_kmeans` with a reasonable k (default 3) and evaluate with
   `compute_silhouette` — if silhouette < 0.3, adjust k or try `run_dbscan`.
3. After selecting the best model, call `compute_cluster_profile` to describe
   each segment.
4. Provide a plain-language interpretation: name each segment (e.g. "High-Value
   Loyal Customers", "At-Risk Churners"), and explain the key differentiating
   features.

Always explain your reasoning to the user and offer actionable recommendations
for each segment."""


# ---------------------------------------------------------------------------
# ClusteringAgent
# ---------------------------------------------------------------------------


class ClusteringAgent(BaseAgent):
    """Agent that performs automated clustering and segment interpretation.

    Parameters
    ----------
    model : BaseChatModel
        Language model powering the ReAct loop.
    create_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to ``create_react_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra keyword arguments forwarded to the react-agent graph's ``invoke``.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer for persistence / HITL.
    system_prompt : str, optional
        Override the default clustering system prompt.
    """

    def __init__(
        self,
        model: Any,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        system_prompt: Optional[str] = None,
    ):
        # NOTE: We do NOT call super().__init__() because BaseAgent tries to
        # assign read-only properties (input_schema, output_schema) from the
        # compiled graph, which raises AttributeError.  The time-series agents
        # follow the same manual-init pattern.
        self._params = {
            "model": model,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "system_prompt": system_prompt or _CLUSTERING_SYSTEM_PROMPT,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    # ------------------------------------------------------------------
    # BaseAgent contract
    # ------------------------------------------------------------------

    def _make_compiled_graph(self):
        self.response = None
        return _build_clustering_graph(
            model=self._params["model"],
            create_react_agent_kwargs=self._params["create_react_agent_kwargs"],
            invoke_react_agent_kwargs=self._params["invoke_react_agent_kwargs"],
            checkpointer=self._params["checkpointer"],
            system_prompt=self._params["system_prompt"],
        )

    def update_params(self, **kwargs):
        """Update parameters and rebuild the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def invoke_agent(
        self,
        user_instructions: str,
        data: Optional[List[List[float]]] = None,
        feature_names: Optional[List[str]] = None,
        **kwargs,
    ):
        """Run the clustering agent end-to-end.

        Parameters
        ----------
        user_instructions : str
            Natural-language task description.
        data              : list[list[float]], optional
            2-D data matrix (n_samples × n_features).
        feature_names     : list[str], optional
            Column names for features.
        **kwargs          : Forwarded to ``self.invoke()``.
        """
        return self.invoke(
            input={
                "user_instructions": user_instructions,
                "data": data or [],
                "feature_names": feature_names or [],
                "cluster_artifacts": {},
                "tool_calls": [],
            },
            **kwargs,
        )

    def get_ai_message(self, markdown: bool = False) -> Optional[Any]:
        """Return the last AI text response."""
        if not self.response:
            return None
        for msg in reversed(self.response.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                text = msg.content
                if markdown and Markdown is not None:
                    return Markdown(text)  # type: ignore[return-value]
                return text
        return None

    def get_artifacts(self) -> Dict[str, Any]:
        """Return accumulated clustering artefacts from the last run."""
        if not self.response:
            return {}
        return self.response.get("cluster_artifacts", {})

    def get_tool_calls(self) -> List[str]:
        """Return a list of tool names that were invoked in the last run."""
        if not self.response:
            return []
        return self.response.get("tool_calls", [])


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------


def _build_clustering_graph(
    model: Any,
    create_react_agent_kwargs: Dict,
    invoke_react_agent_kwargs: Dict,
    checkpointer: Optional[Checkpointer],
    system_prompt: str,
):
    """Build and compile the ClusteringAgent state graph."""

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        data: List[List[float]]
        feature_names: List[str]
        cluster_artifacts: Dict[str, Any]
        tool_calls: List[str]

    react_agent_graph = create_agent(
        model,
        tools=_CLUSTERING_TOOLS,
        state_schema=GraphState,  # type: ignore[arg-type]
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    # ---- nodes ------------------------------------------------------------

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name("ClusteringAgent"))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        data = state.get("data", [])
        feature_names = state.get("feature_names", [])
        n_samples = len(data)
        n_features = len(data[0]) if data else 0

        context = f"[Data: {n_samples} samples × {n_features} features"
        if feature_names:
            context += f"; features: {', '.join(feature_names)}"
        context += "]"

        instructions = state.get("user_instructions", "Cluster the data.")
        return {"messages": [("user", f"{instructions}\n\n{context}")]}

    def run_react_agent(state: GraphState):
        logger.info("    * RUN REACT TOOL-CALLING AGENT [CLUSTERING]")
        response = react_agent_graph.invoke(state, **invoke_react_agent_kwargs)  # type: ignore[arg-type]
        tool_names = get_tool_call_names(response.get("messages", []))
        return {
            "messages": response.get("messages", []),
            "tool_calls": tool_names,
        }

    def post_process(state: GraphState):
        logger.info("    * POST PROCESS")
        # Collect artefacts from all tool result messages that carry JSON

        artifacts: Dict[str, Any] = {}
        for msg in state.get("messages", []):
            # ToolMessages from content_and_artifact tools carry .artifact
            if hasattr(msg, "artifact") and isinstance(msg.artifact, dict):
                key = str(getattr(msg, "name", "result"))
                artifacts[key] = msg.artifact
        return {"cluster_artifacts": artifacts}

    # ---- graph wiring -----------------------------------------------------

    builder = StateGraph(GraphState)
    builder.add_node("prepare_messages", prepare_messages)
    builder.add_node("run_react_agent", run_react_agent)
    builder.add_node("post_process", post_process)

    builder.add_edge(START, "prepare_messages")
    builder.add_edge("prepare_messages", "run_react_agent")
    builder.add_edge("run_react_agent", "post_process")
    builder.add_edge("post_process", END)

    return builder.compile(checkpointer=checkpointer, name="ClusteringAgent")
