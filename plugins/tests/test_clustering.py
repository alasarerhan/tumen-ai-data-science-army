"""Tests for M14 — Clustering tools and ClusteringAgent.

Tool tests run without a real LLM (direct .func() calls).
Agent construction tests use a deterministic FakeChatModel mock.
"""

from __future__ import annotations

import random
from typing import List

import numpy as np

# ---------------------------------------------------------------------------
# Helpers — synthetic data
# ---------------------------------------------------------------------------


def _make_blob_data(
    n_per_cluster: int = 30,
    centers: List[List[float]] = None,
    noise: float = 0.3,
    seed: int = 42,
) -> List[List[float]]:
    """Generate isotropic Gaussian blobs around given centers."""
    if centers is None:
        centers = [[0.0, 0.0], [5.0, 5.0], [10.0, 0.0]]
    rng = random.Random(seed)
    points = []
    for cx, cy in centers:
        for _ in range(n_per_cluster):
            points.append([cx + rng.gauss(0, noise), cy + rng.gauss(0, noise)])
    return points


def _make_random_data(n: int = 50, n_features: int = 4, seed: int = 0) -> List[List[float]]:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, n_features)).tolist()


# ===========================================================================
# Tool tests — run_kmeans
# ===========================================================================


def test_kmeans_returns_labels():
    from ai_data_science_team.tools.e12_clustering import run_kmeans

    data = _make_blob_data()
    text, result = run_kmeans.func(data=data, n_clusters=3, random_state=0)
    assert "labels" in result
    assert len(result["labels"]) == len(data)
    assert "K-Means" in text


def test_kmeans_correct_n_clusters():
    from ai_data_science_team.tools.e12_clustering import run_kmeans

    data = _make_blob_data(n_per_cluster=20, centers=[[0, 0], [10, 10]])
    _, result = run_kmeans.func(data=data, n_clusters=2, random_state=42)
    assert result["n_clusters"] == 2
    assert set(result["labels"]).issubset({0, 1})


def test_kmeans_inertia_positive():
    from ai_data_science_team.tools.e12_clustering import run_kmeans

    data = _make_blob_data()
    _, result = run_kmeans.func(data=data, n_clusters=3, random_state=0)
    assert result["inertia"] > 0


def test_kmeans_silhouette_range():
    from ai_data_science_team.tools.e12_clustering import run_kmeans

    data = _make_blob_data()
    _, result = run_kmeans.func(data=data, n_clusters=3, random_state=0)
    sil = result["silhouette_score"]
    assert sil is not None
    assert -1.0 <= sil <= 1.0


def test_kmeans_centroids_shape():
    from ai_data_science_team.tools.e12_clustering import run_kmeans

    data = _make_blob_data()
    _, result = run_kmeans.func(data=data, n_clusters=3, random_state=0)
    # Each centroid should have 2 coordinates (matching the 2-D data)
    assert all(len(c) == 2 for c in result["centroids"])


def test_kmeans_cluster_sizes_sum():
    from ai_data_science_team.tools.e12_clustering import run_kmeans

    data = _make_blob_data()
    _, result = run_kmeans.func(data=data, n_clusters=3)
    total = sum(result["cluster_sizes"].values())
    assert total == len(data)


# ===========================================================================
# Tool tests — run_dbscan
# ===========================================================================


def test_dbscan_returns_labels():
    from ai_data_science_team.tools.e12_clustering import run_dbscan

    data = _make_blob_data(noise=0.2)
    text, result = run_dbscan.func(data=data, eps=0.5, min_samples=3)
    assert "labels" in result
    assert len(result["labels"]) == len(data)
    assert "DBSCAN" in text


def test_dbscan_finds_clusters():
    from ai_data_science_team.tools.e12_clustering import run_dbscan

    data = _make_blob_data(noise=0.15, centers=[[0, 0], [10, 10]])
    _, result = run_dbscan.func(data=data, eps=0.5, min_samples=3)
    assert result["n_clusters"] >= 2


def test_dbscan_noise_count_type():
    from ai_data_science_team.tools.e12_clustering import run_dbscan

    data = _make_blob_data()
    _, result = run_dbscan.func(data=data, eps=0.5, min_samples=3)
    assert isinstance(result["noise_count"], int)
    assert result["noise_count"] >= 0


def test_dbscan_result_keys():
    from ai_data_science_team.tools.e12_clustering import run_dbscan

    data = _make_blob_data()
    _, result = run_dbscan.func(data=data, eps=0.5, min_samples=3)
    for k in (
        "labels",
        "n_clusters",
        "noise_count",
        "core_sample_count",
        "cluster_sizes",
        "eps",
        "min_samples",
    ):
        assert k in result


# ===========================================================================
# Tool tests — reduce_pca
# ===========================================================================


def test_pca_output_shape():
    from ai_data_science_team.tools.e12_clustering import reduce_pca

    data = _make_random_data(n=50, n_features=6)
    text, result = reduce_pca.func(data=data, n_components=2)
    transformed = result["transformed"]
    assert len(transformed) == 50
    assert all(len(row) == 2 for row in transformed)
    assert "PCA" in text


def test_pca_explained_variance_sums_to_one():
    from ai_data_science_team.tools.e12_clustering import reduce_pca

    data = _make_random_data(n=60, n_features=4)
    _, result = reduce_pca.func(data=data, n_components=4)
    total = sum(result["explained_variance_ratio"])
    assert abs(total - 1.0) < 1e-4


def test_pca_result_keys():
    from ai_data_science_team.tools.e12_clustering import reduce_pca

    data = _make_random_data()
    _, result = reduce_pca.func(data=data, n_components=2)
    for k in (
        "transformed",
        "explained_variance_ratio",
        "cumulative_variance",
        "n_components",
        "component_loadings",
        "feature_names",
    ):
        assert k in result


def test_pca_cumulative_variance_correct():
    from ai_data_science_team.tools.e12_clustering import reduce_pca

    data = _make_random_data(n=50, n_features=4)
    _, result = reduce_pca.func(data=data, n_components=2)
    expected = sum(result["explained_variance_ratio"])
    assert abs(result["cumulative_variance"] - expected) < 1e-6


# ===========================================================================
# Tool tests — reduce_tsne
# ===========================================================================


def test_tsne_output_shape():
    from ai_data_science_team.tools.e12_clustering import reduce_tsne

    data = _make_random_data(n=30, n_features=4)
    text, result = reduce_tsne.func(
        data=data, n_components=2, perplexity=5.0, max_iter=250, random_state=0
    )
    transformed = result["transformed"]
    assert len(transformed) == 30
    assert all(len(row) == 2 for row in transformed)
    assert "t-SNE" in text


def test_tsne_result_keys():
    from ai_data_science_team.tools.e12_clustering import reduce_tsne

    data = _make_random_data(n=20, n_features=3)
    _, result = reduce_tsne.func(
        data=data, n_components=2, perplexity=3.0, max_iter=300, random_state=0
    )
    for k in ("transformed", "n_components", "kl_divergence", "n_iter", "perplexity_used"):
        assert k in result


def test_tsne_kl_divergence_positive():
    from ai_data_science_team.tools.e12_clustering import reduce_tsne

    data = _make_random_data(n=20, n_features=3)
    _, result = reduce_tsne.func(
        data=data, n_components=2, perplexity=3.0, max_iter=300, random_state=42
    )
    assert result["kl_divergence"] >= 0


# ===========================================================================
# Tool tests — compute_cluster_profile
# ===========================================================================


def test_cluster_profile_keys():
    from ai_data_science_team.tools.e12_clustering import compute_cluster_profile

    data = _make_blob_data()
    labels = [0] * 30 + [1] * 30 + [2] * 30
    text, result = compute_cluster_profile.func(data=data, labels=labels, feature_names=["x", "y"])
    assert "profiles" in result
    assert "0" in result["profiles"]
    assert "Cluster Profile" in text


def test_cluster_profile_sizes_correct():
    from ai_data_science_team.tools.e12_clustering import compute_cluster_profile

    data = _make_blob_data()
    labels = [0] * 30 + [1] * 30 + [2] * 30
    _, result = compute_cluster_profile.func(data=data, labels=labels)
    for key in ("0", "1", "2"):
        assert result["profiles"][key]["size"] == 30
        assert abs(result["profiles"][key]["share"] - 1 / 3) < 0.01


def test_cluster_profile_mean_length():
    from ai_data_science_team.tools.e12_clustering import compute_cluster_profile

    data = _make_random_data(n=40, n_features=5)
    labels = [i % 4 for i in range(40)]
    _, result = compute_cluster_profile.func(data=data, labels=labels)
    for stats in result["profiles"].values():
        assert len(stats["mean"]) == 5


# ===========================================================================
# Tool tests — compute_silhouette
# ===========================================================================


def test_silhouette_range():
    from ai_data_science_team.tools.e12_clustering import compute_silhouette

    data = _make_blob_data()
    labels = [0] * 30 + [1] * 30 + [2] * 30
    text, result = compute_silhouette.func(data=data, labels=labels)
    sil = result["overall_silhouette"]
    assert sil is not None
    assert -1.0 <= sil <= 1.0
    assert "Silhouette" in text


def test_silhouette_single_cluster_returns_none():
    from ai_data_science_team.tools.e12_clustering import compute_silhouette

    data = _make_blob_data()
    labels = [0] * len(data)
    _, result = compute_silhouette.func(data=data, labels=labels)
    assert result["overall_silhouette"] is None


def test_silhouette_result_keys():
    from ai_data_science_team.tools.e12_clustering import compute_silhouette

    data = _make_blob_data()
    labels = [0] * 30 + [1] * 30 + [2] * 30
    _, result = compute_silhouette.func(data=data, labels=labels)
    for k in ("overall_silhouette", "per_cluster_silhouette", "n_valid_samples", "n_clusters"):
        assert k in result


def test_silhouette_per_cluster_count():
    from ai_data_science_team.tools.e12_clustering import compute_silhouette

    data = _make_blob_data()
    labels = [0] * 30 + [1] * 30 + [2] * 30
    _, result = compute_silhouette.func(data=data, labels=labels)
    assert len(result["per_cluster_silhouette"]) == 3


# ===========================================================================
# Fake LLM helper
# ===========================================================================


def _fake_llm():
    """Minimal stub satisfying BaseAgent graph construction (no API key)."""
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage as LCAIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class FakeChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "fake"

        def _generate(self, messages, stop=None, _run_manager=None, **kw) -> ChatResult:
            return ChatResult(generations=[ChatGeneration(message=LCAIMessage(content="Done."))])

        def bind_tools(self, tools, **kw):
            return self

    return FakeChatModel()


# ===========================================================================
# Agent construction tests — ClusteringAgent
# ===========================================================================


def test_clustering_agent_instantiation():
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_artifacts")
    assert hasattr(agent, "get_ai_message")


def test_clustering_agent_nodes_present():
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)
    assert any("post" in n for n in node_names)


def test_clustering_agent_update_params_rebuilds_graph():
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=_fake_llm())
    original_graph = agent._compiled_graph
    agent.update_params(system_prompt="New prompt.")
    assert agent._compiled_graph is not original_graph


def test_clustering_agent_exported_from_init():
    from ai_data_science_team.ml_agents import ClusteringAgent  # noqa: F401

    assert ClusteringAgent is not None


def test_clustering_agent_get_ai_message_returns_none_before_invoke():
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=_fake_llm())
    assert agent.get_ai_message() is None


def test_clustering_agent_get_artifacts_returns_empty_before_invoke():
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=_fake_llm())
    assert agent.get_artifacts() == {}


def test_clustering_agent_get_tool_calls_returns_empty_before_invoke():
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=_fake_llm())
    assert agent.get_tool_calls() == []
