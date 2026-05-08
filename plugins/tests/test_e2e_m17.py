"""M17 TG3 — Human-in-the-Loop E2E Akis Testi.

Tam onay dongusu: bir analiz ajaninin ciktisi ApprovalGateAgent'a sunulur,
insan onay duraklama noktasindan gectikten sonra is akisi tamamlanir.

Senaryo:
  1. ResultsSynthesizerAgent  → bulgulari birlestir + sirala
  2. ApprovalGateAgent (HITL) → sentetik analizi insan onay noktasina sun
  3. Onay kararı  → "yes" ile devam
  4. Son mesaj + artifacts dogrulama

Calistirmak icin:
    python -m pytest tests/test_e2e_m17.py -v -m integration
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

_UPSTREAM = {
    "ClusteringAgent": {"n_clusters": 3, "silhouette_score": 0.71},
    "AutoForecastAgent": {"best_model": "AutoARIMA", "rmse": 142.3},
}


def _inv(agent, **kw):
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run E2E tests")
        raise


def _resume(agent, decision, config):
    try:
        agent.resume_agent(decision=decision, config=config)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run E2E tests")
        raise


@pytest.fixture(scope="module")
def llm():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=500)


# ---------------------------------------------------------------------------
# E2E: synthesize → HITL approve → done
# ---------------------------------------------------------------------------


@skip_no_key
def test_e2e_hitl_synthesize_then_approve(llm):
    """Stage 1: synthesize findings. Stage 2: HITL interrupt + yes-approve."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    # --- Stage 1: synthesize ---
    synth = ResultsSynthesizerAgent(model=llm)
    _inv(
        synth,
        user_instructions=(
            "Merge the clustering and forecasting results and rank the top findings."
        ),
        prior_artifacts=_UPSTREAM,
    )
    synth_artifacts = synth.get_artifacts()
    assert isinstance(synth_artifacts, dict), "Synthesizer must return a dict"

    # --- Stage 2: HITL review & approve ---
    config = {"configurable": {"thread_id": "e2e-hitl-approve-tg3"}}
    approval = ApprovalGateAgent(model=llm, human_in_the_loop=True)
    _inv(
        approval,
        user_instructions=(
            "Summarise the synthesis findings for human review. One paragraph."
        ),
        prior_artifacts=synth_artifacts,
        config=config,
    )

    state = approval.get_state(config)
    assert state is not None, "Graph state must be accessible at interrupt point"

    # Approve
    _resume(approval, decision="yes", config=config)

    final_msg = approval.get_ai_message()
    assert isinstance(final_msg, str) and len(final_msg) > 0, (
        "ApprovalGateAgent must produce a non-empty message after approval"
    )
    final_artifacts = approval.get_artifacts()
    assert isinstance(final_artifacts, dict), (
        "ApprovalGateAgent artifacts must be a dict"
    )


@skip_no_key
def test_e2e_hitl_synthesize_then_modify_and_approve(llm):
    """Stage 1: synthesize. Stage 2: HITL with modification request, then approve."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    # Stage 1
    synth = ResultsSynthesizerAgent(model=llm)
    _inv(
        synth,
        user_instructions="Extract key metrics and compare to baseline rmse=180.",
        prior_artifacts=_UPSTREAM,
    )
    synth_artifacts = synth.get_artifacts()

    # Stage 2a: invoke → interrupt
    config = {"configurable": {"thread_id": "e2e-hitl-modify-tg3"}}
    approval = ApprovalGateAgent(model=llm, human_in_the_loop=True)
    _inv(
        approval,
        user_instructions="Prepare a concise approval brief for these findings.",
        prior_artifacts=synth_artifacts,
        config=config,
    )

    # Stage 2b: request modification
    _resume(
        approval,
        decision="Please add a risk level (low/medium/high) to the brief.",
        config=config,
    )

    final_msg = approval.get_ai_message()
    assert isinstance(final_msg, str) and len(final_msg) > 0, (
        "ApprovalGateAgent must produce a non-empty message after modification"
    )


@skip_no_key
def test_e2e_hitl_no_interrupt_full_flow(llm):
    """Non-HITL mode: synthesize → gate (no interrupt) → final message in one pass."""
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    synth = ResultsSynthesizerAgent(model=llm)
    _inv(
        synth,
        user_instructions="Rank all findings by business impact.",
        prior_artifacts=_UPSTREAM,
    )

    gate = ApprovalGateAgent(model=llm, human_in_the_loop=False)
    _inv(
        gate,
        user_instructions="Review and approve the synthesis results. One paragraph summary.",
        prior_artifacts=synth.get_artifacts(),
    )

    msg = gate.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0, (
        "No-HITL flow must produce a final AI message without manual intervention"
    )
