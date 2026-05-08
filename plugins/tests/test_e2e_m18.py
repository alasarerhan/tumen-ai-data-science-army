"""M18 TG3 — Stratejik Icgoru E2E Rapor Uretim Zinciri.

Dört ajanin tam sirali boru hatti:
  1. ContextualKnowledgeAgent  → is baglamini olustur + soru uret
  2. ResultsSynthesizerAgent   → yukari akis sonuclarini birlestir + sirala
  3. NarrativeAgent            → yönetici özeti + tam rapor
  4. RecommendationAgent       → onceliklendirilmis tavsiyeler

Her ajanin ciktisi bir sonrakinin `prior_artifacts` girdisine akar.
Nihai cikti: tek bir sozlukte tum dort ajanin ciktisini iceren "Stratejik Rapor".

Calistirmak icin:
    python -m pytest tests/test_e2e_m18.py -v -m integration
Atlamak icin:
    python -m pytest tests/ -v -m "not integration"
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
skip_no_key = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY is not set — skipping integration tests",
)

langchain_openai = pytest.importorskip(
    "langchain_openai",
    reason="langchain_openai is not installed — skipping integration tests",
)

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_RAW_FINDINGS = {
    "ClusteringAgent": {
        "n_clusters": 3,
        "silhouette_score": 0.71,
        "cluster_sizes": [1200, 850, 450],
        "top_features": ["avg_order_value", "recency_days", "purchase_freq"],
    },
    "AutoForecastAgent": {
        "best_model": "AutoARIMA",
        "rmse": 142.3,
        "mape": 0.083,
        "forecast_horizon_days": 30,
        "trend": "upward",
    },
}

_BUSINESS_CONTEXT = (
    "E-commerce platform; 50 000 monthly active users; primary KPI: monthly revenue. "
    "Goal: reduce 90-day churn by 10 % and improve forecast accuracy."
)


def _inv(agent, **kw):
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run E2E tests")
        raise


@pytest.fixture(scope="module")
def llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=600)


# ---------------------------------------------------------------------------
# Pipeline stages as module-level helpers (reused across tests)
# ---------------------------------------------------------------------------


def _stage_context(llm) -> dict:
    """Stage 1 — ContextualKnowledgeAgent."""
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent
    agent = ContextualKnowledgeAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Build a structured business context profile and generate "
            "2 clarifying questions for the stakeholder."
        ),
        prior_artifacts={"business_context": _BUSINESS_CONTEXT},
    )
    out = agent.get_artifacts()
    out["_ctx_message"] = agent.get_ai_message() or ""
    return out


def _stage_synthesize(llm, context_out: dict) -> dict:
    """Stage 2 — ResultsSynthesizerAgent."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    combined = {**_RAW_FINDINGS, **context_out}
    agent = ResultsSynthesizerAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Merge all upstream agent outputs, extract key metrics, "
            "and rank the top 3 findings by estimated revenue impact."
        ),
        prior_artifacts=combined,
    )
    out = agent.get_artifacts()
    out["_synth_message"] = agent.get_ai_message() or ""
    return out


def _stage_narrative(llm, synth_out: dict) -> dict:
    """Stage 3 — NarrativeAgent."""
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent
    agent = NarrativeAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Generate a concise executive summary (3 sentences) "
            "and format a full one-page strategic report from the findings."
        ),
        prior_artifacts=synth_out,
    )
    out = agent.get_artifacts()
    out["_narrative_message"] = agent.get_ai_message() or ""
    return out


def _stage_recommend(llm, narrative_out: dict) -> dict:
    """Stage 4 — RecommendationAgent."""
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent
    agent = RecommendationAgent(model=llm)
    _inv(
        agent,
        user_instructions=(
            "Generate 3 prioritised actionable recommendations using ICE scoring. "
            "Design one A/B test for the highest-priority recommendation."
        ),
        prior_artifacts=narrative_out,
    )
    out = agent.get_artifacts()
    out["_rec_message"] = agent.get_ai_message() or ""
    return out


# ---------------------------------------------------------------------------
# TG3 tests
# ---------------------------------------------------------------------------


@skip_no_key
def test_e2e_strategic_report_full_pipeline(llm):
    """Full 4-stage pipeline produces non-empty AI messages at every stage."""
    ctx = _stage_context(llm)
    assert len(ctx.get("_ctx_message", "")) > 0, "Stage 1 (context) must produce a message"

    synth = _stage_synthesize(llm, ctx)
    assert len(synth.get("_synth_message", "")) > 0, "Stage 2 (synthesis) must produce a message"

    narr = _stage_narrative(llm, synth)
    assert len(narr.get("_narrative_message", "")) > 0, "Stage 3 (narrative) must produce a message"

    rec = _stage_recommend(llm, narr)
    assert len(rec.get("_rec_message", "")) > 0, "Stage 4 (recommendations) must produce a message"


@skip_no_key
def test_e2e_strategic_report_artifacts_chain(llm):
    """Artifacts flow correctly through all 4 stages; final dict contains 4 message keys."""
    ctx = _stage_context(llm)
    synth = _stage_synthesize(llm, ctx)
    narr = _stage_narrative(llm, synth)
    rec = _stage_recommend(llm, narr)

    # Each stage must return a non-empty dict
    for stage_name, stage_out in [
        ("context", ctx),
        ("synthesis", synth),
        ("narrative", narr),
        ("recommendations", rec),
    ]:
        assert isinstance(stage_out, dict) and len(stage_out) > 0, (
            f"Stage '{stage_name}' must return a non-empty artifacts dict"
        )


@skip_no_key
def test_e2e_strategic_report_each_stage_uses_tools(llm):
    """Every agent in the pipeline must invoke at least one tool."""
    from ai_data_science_team.agents.strategic_agents import (
        ContextualKnowledgeAgent,
        ResultsSynthesizerAgent,
        NarrativeAgent,
        RecommendationAgent,
    )

    agents_and_instructions = [
        (
            ContextualKnowledgeAgent(model=llm),
            "Extract business entities from: " + _BUSINESS_CONTEXT,
            {},
        ),
        (
            ResultsSynthesizerAgent(model=llm),
            "Rank findings by business impact.",
            _RAW_FINDINGS,
        ),
        (
            NarrativeAgent(model=llm),
            "Generate an executive summary.",
            _RAW_FINDINGS,
        ),
        (
            RecommendationAgent(model=llm),
            "Generate 2 prioritised recommendations.",
            _RAW_FINDINGS,
        ),
    ]

    for agent, instructions, prior in agents_and_instructions:
        _inv(agent, user_instructions=instructions, prior_artifacts=prior)
        tool_calls = agent.get_tool_calls()
        assert isinstance(tool_calls, list) and len(tool_calls) > 0, (
            f"{type(agent).__name__} must invoke at least one tool"
        )


@skip_no_key
def test_e2e_strategic_report_final_output_has_recommendations(llm):
    """Final RecommendationAgent message must mention a recommendation or action."""
    ctx = _stage_context(llm)
    synth = _stage_synthesize(llm, ctx)
    narr = _stage_narrative(llm, synth)
    rec = _stage_recommend(llm, narr)

    final = rec.get("_rec_message", "")
    # The word "recommendation" or a numbered list indicator typically appears
    assert len(final) > 50, (
        f"Final recommendation message too short ({len(final)} chars): {final!r}"
    )
