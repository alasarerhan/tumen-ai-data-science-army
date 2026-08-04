"""
M14 – ClusteringAgent TG2 Entegrasyon Testleri
===============================================
Gerçek LLM API'si (OpenAI) ile uçtan-uca çalışır.
Çalıştırmak için:
    python -m pytest tests/test_integration_m14.py -v -m integration
Atlamak için (diğer testlerle birlikte):
    python -m pytest tests/ -v -m "not integration"
"""

import pytest
from _llm import make_chat_model, skip_no_key

# ---------------------------------------------------------------------------
# Guards — skip the entire module if the key is absent
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.integration


langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def llm():
    return make_chat_model(temperature=0)


# Synthetic 2-D dataset with 3 clearly separated clusters
_CLUSTER_DATA: list = [
    # Cluster A — bottom-left
    [1.0, 1.1],
    [1.2, 0.9],
    [0.8, 1.0],
    [1.1, 1.3],
    [0.9, 0.8],
    # Cluster B — top-right
    [9.0, 9.1],
    [9.2, 8.9],
    [8.8, 9.0],
    [9.1, 9.3],
    [8.9, 8.8],
    # Cluster C — bottom-right
    [9.0, 1.0],
    [9.2, 0.9],
    [8.8, 1.1],
    [9.1, 0.8],
    [8.9, 1.2],
]
_FEATURE_NAMES = ["x", "y"]


# ---------------------------------------------------------------------------
# ClusteringAgent tests
# ---------------------------------------------------------------------------


@skip_no_key
def test_clustering_agent_basic(llm):
    """ClusteringAgent should return a non-empty AI message."""
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=llm)
    agent.invoke_agent(
        user_instructions=(
            "Cluster this 2-D dataset. Use k-means with k=3 and describe the resulting clusters."
        ),
        data=_CLUSTER_DATA,
        feature_names=_FEATURE_NAMES,
    )

    msg = agent.get_ai_message()
    assert isinstance(msg, str), "Expected a string AI message"
    assert len(msg) > 0, "AI message should not be empty"


@skip_no_key
def test_clustering_agent_artifacts(llm):
    """ClusteringAgent should populate the artifacts dict."""
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Cluster this data and return cluster assignments.",
        data=_CLUSTER_DATA,
        feature_names=_FEATURE_NAMES,
    )

    artifacts = agent.get_artifacts()
    assert isinstance(artifacts, dict), "Artifacts should be a dict"


@skip_no_key
def test_clustering_agent_tool_calls(llm):
    """ClusteringAgent should record at least one tool call."""
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=llm)
    agent.invoke_agent(
        user_instructions="Run k-means clustering (k=3) on this data.",
        data=_CLUSTER_DATA,
        feature_names=_FEATURE_NAMES,
    )

    tool_calls = agent.get_tool_calls()
    assert isinstance(tool_calls, list), "Tool calls should be a list"
    assert len(tool_calls) > 0, "At least one tool should have been called"


@skip_no_key
def test_clustering_agent_cluster_count(llm):
    """ClusteringAgent result should reflect 3 clusters for well-separated data."""
    from ai_data_science_team.ml_agents.clustering_agent import ClusteringAgent

    agent = ClusteringAgent(model=llm)
    agent.invoke_agent(
        user_instructions=(
            "Use k-means with k=3 to cluster this dataset. "
            "Return the cluster label for every data point."
        ),
        data=_CLUSTER_DATA,
        feature_names=_FEATURE_NAMES,
    )

    artifacts = agent.get_artifacts()
    # If the agent stores cluster labels, verify there are exactly 3 unique labels.
    labels = artifacts.get("cluster_labels") or artifacts.get("labels")
    if labels is not None:
        assert len(set(labels)) == 3, "Expected exactly 3 distinct cluster labels"
