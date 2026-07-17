"""
M18 - Stratejik Icgoru Supervizoru TG2 Entegrasyon Testleri
=============================================================
Gercek LLM API (OpenAI) ile uctan-uca calisir.
Calistirmak icin:
    python -m pytest tests/test_integration_m18.py -v -m integration
Atlamak icin:
    python -m pytest tests/ -v -m "not integration"
"""

import pytest

from _llm import make_chat_model, skip_no_key

pytestmark = pytest.mark.integration



langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)

_UPSTREAM = {
    "ClusteringAgent": {
        "n_clusters": 3,
        "silhouette_score": 0.71,
        "cluster_sizes": [1200, 850, 450],
    },
    "AutoForecastAgent": {
        "best_model": "AutoARIMA",
        "rmse": 142.3,
        "mape": 0.083,
        "forecast_horizon_days": 30,
    },
}

_BIZ = (
    "E-commerce company. KPI: monthly revenue. "
    "50 000 active users. Goal: reduce churn and improve LTV segmentation."
)


def _inv(agent, **kw):
    """Invoke agent; skip gracefully if OpenAI quota is exhausted."""
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run integration tests")
        raise


@pytest.fixture(scope="module")
def llm():
    return make_chat_model(temperature=0, max_tokens=500)


# ---------------------------------------------------------------------------
# ResultsSynthesizerAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_results_synthesizer_basic(llm):
    """ResultsSynthesizerAgent should return a non-empty AI message."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    agent = ResultsSynthesizerAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Merge the clustering and forecasting results, extract key metrics, "
             "and rank the top 3 findings by business impact."
         ),
         prior_artifacts=_UPSTREAM)
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_results_synthesizer_artifacts(llm):
    """ResultsSynthesizerAgent should populate artifacts dict."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    agent = ResultsSynthesizerAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Extract key metrics and compare them against baseline: rmse=180, silhouette=0.55."
         ),
         prior_artifacts=_UPSTREAM)
    assert isinstance(agent.get_artifacts(), dict)


@skip_no_key
def test_results_synthesizer_tool_calls(llm):
    """ResultsSynthesizerAgent should invoke at least one synthesis tool."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    agent = ResultsSynthesizerAgent(model=llm)
    _inv(agent,
         user_instructions="Rank the findings from the downstream agents by potential revenue impact.",
         prior_artifacts=_UPSTREAM)
    tool_calls = agent.get_tool_calls()
    assert isinstance(tool_calls, list) and len(tool_calls) > 0


# ---------------------------------------------------------------------------
# ContextualKnowledgeAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_contextual_knowledge_agent_basic(llm):
    """ContextualKnowledgeAgent should return a non-empty AI message."""
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent
    agent = ContextualKnowledgeAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Build a context profile for the following business and "
             "generate two clarifying questions for the stakeholder."
         ),
         prior_artifacts={"business_context": _BIZ})
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_contextual_knowledge_agent_tool_calls(llm):
    """ContextualKnowledgeAgent should invoke at least one knowledge tool."""
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent
    agent = ContextualKnowledgeAgent(model=llm)
    _inv(agent,
         user_instructions="Extract business entities from: " + _BIZ,
         prior_artifacts={})
    assert isinstance(agent.get_tool_calls(), list) and len(agent.get_tool_calls()) > 0


# ---------------------------------------------------------------------------
# NarrativeAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_narrative_agent_executive_summary(llm):
    """NarrativeAgent should produce an executive summary."""
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent
    agent = NarrativeAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Generate a concise executive summary (max 3 sentences) "
             "based on the clustering and forecasting findings."
         ),
         prior_artifacts=_UPSTREAM)
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_narrative_agent_tool_calls(llm):
    """NarrativeAgent should invoke at least one narrative tool."""
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent
    agent = NarrativeAgent(model=llm)
    _inv(agent,
         user_instructions="Format a one-page strategic report from the provided agent results.",
         prior_artifacts=_UPSTREAM)
    assert isinstance(agent.get_tool_calls(), list) and len(agent.get_tool_calls()) > 0


# ---------------------------------------------------------------------------
# RecommendationAgent
# ---------------------------------------------------------------------------


@skip_no_key
def test_recommendation_agent_basic(llm):
    """RecommendationAgent should return a non-empty AI message with recommendations."""
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent
    agent = RecommendationAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Generate 3 prioritised actionable recommendations to improve "
             "revenue forecasting accuracy and customer segmentation quality."
         ),
         prior_artifacts=_UPSTREAM)
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_recommendation_agent_artifacts(llm):
    """RecommendationAgent should return a dict from get_artifacts()."""
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent
    agent = RecommendationAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Prioritise these three actions using ICE scoring: "
             "1) Retrain forecast model weekly. "
             "2) Add customer LTV feature. "
             "3) Deploy A/B test for personalization."
         ),
         prior_artifacts=_UPSTREAM)
    assert isinstance(agent.get_artifacts(), dict)


@skip_no_key
def test_recommendation_agent_tool_calls(llm):
    """RecommendationAgent should invoke at least one recommendation tool."""
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent
    agent = RecommendationAgent(model=llm)
    _inv(agent,
         user_instructions=(
             "Design an A/B test to validate whether weekly model retraining "
             "significantly reduces RMSE compared to monthly retraining."
         ),
         prior_artifacts=_UPSTREAM)
    assert isinstance(agent.get_tool_calls(), list) and len(agent.get_tool_calls()) > 0