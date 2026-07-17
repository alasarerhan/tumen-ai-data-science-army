"""
M17 - Human-in-the-Loop (HITL) TG2 Entegrasyon Testleri
=========================================================
Gercek LLM API (OpenAI) ile uctan-uca calisir.
Calistirmak icin:
    python -m pytest tests/test_integration_m17.py -v -m integration
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

_PRIOR = {
    "ClusteringAgent": {"n_clusters": 3, "silhouette": 0.71},
    "AutoForecastAgent": {"best_model": "AutoARIMA", "rmse": 142.3},
}


def _inv(agent, **kw):
    """Invoke agent; skip gracefully if OpenAI quota is exhausted."""
    try:
        agent.invoke_agent(**kw)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run integration tests")
        raise


def _resume(agent, decision, config):
    """Resume agent; skip gracefully if OpenAI quota is exhausted."""
    try:
        agent.resume_agent(decision=decision, config=config)
    except Exception as exc:
        if "insufficient_quota" in str(exc) or "RateLimitError" in type(exc).__name__:
            pytest.skip("OpenAI quota exhausted — add billing to run integration tests")
        raise


@pytest.fixture(scope="module")
def llm():
    return make_chat_model(temperature=0, max_tokens=400)


# ---------------------------------------------------------------------------
# human_in_the_loop=False  (normal flow)
# ---------------------------------------------------------------------------


@skip_no_key
def test_approval_gate_no_hitl_basic(llm):
    """ApprovalGateAgent (no HITL) should return a non-empty AI message."""
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent
    agent = ApprovalGateAgent(model=llm, human_in_the_loop=False)
    _inv(agent,
         user_instructions="Review the clustering and forecasting results. Summarise in two sentences.",
         prior_artifacts=_PRIOR)
    msg = agent.get_ai_message()
    assert isinstance(msg, str) and len(msg) > 0


@skip_no_key
def test_approval_gate_no_hitl_artifacts(llm):
    """ApprovalGateAgent (no HITL) should return a dict from get_artifacts()."""
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent
    agent = ApprovalGateAgent(model=llm, human_in_the_loop=False)
    _inv(agent,
         user_instructions="Create an approval summary for the churn analysis results.",
         prior_artifacts={"ChurnModel": {"auc": 0.88, "n_features": 12}})
    assert isinstance(agent.get_artifacts(), dict)


@skip_no_key
def test_approval_gate_no_hitl_tool_calls(llm):
    """ApprovalGateAgent (no HITL) should record at least one tool call."""
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent
    agent = ApprovalGateAgent(model=llm, human_in_the_loop=False)
    _inv(agent,
         user_instructions="Format an approval notification for the following forecast results.",
         prior_artifacts=_PRIOR)
    tool_calls = agent.get_tool_calls()
    assert isinstance(tool_calls, list) and len(tool_calls) > 0


# ---------------------------------------------------------------------------
# human_in_the_loop=True  (interrupt + resume flow)
# ---------------------------------------------------------------------------


@skip_no_key
def test_approval_gate_hitl_interrupt_and_approve(llm):
    """ApprovalGateAgent (HITL=True) should pause then complete after yes."""
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent
    config = {"configurable": {"thread_id": "integration-test-approve-1"}}
    agent = ApprovalGateAgent(model=llm, human_in_the_loop=True)
    _inv(agent,
         user_instructions="Summarise the ML pipeline results for human review in one paragraph.",
         prior_artifacts=_PRIOR,
         config=config)
    state = agent.get_state(config)
    assert state is not None, "Graph state should be accessible after interrupt"
    _resume(agent, decision="yes", config=config)
    final_msg = agent.get_ai_message()
    assert isinstance(final_msg, str) and len(final_msg) > 0


@skip_no_key
def test_approval_gate_hitl_resume_with_modification(llm):
    """ApprovalGateAgent (HITL=True) should re-run after a modification request."""
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent
    config = {"configurable": {"thread_id": "integration-test-modify-1"}}
    agent = ApprovalGateAgent(model=llm, human_in_the_loop=True)
    _inv(agent,
         user_instructions="Prepare an approval summary for the segmentation results.",
         prior_artifacts={"SegmentAgent": {"n_segments": 4, "avg_ltv": 820.5}},
         config=config)
    _resume(agent, decision="Please also include a risk assessment in the summary.", config=config)
    final_msg = agent.get_ai_message()
    assert isinstance(final_msg, str) and len(final_msg) > 0