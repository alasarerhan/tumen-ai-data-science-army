"""Tests for M18 — Strategic Insights Supervisor agents and tools.

Tool tests call ``.func()`` directly (no LLM required).
Agent construction tests use a deterministic FakeChatModel stub.
"""

from __future__ import annotations

import json

import pytest

# ===========================================================================
# Fake LLM helper
# ===========================================================================


def _fake_llm():
    """Minimal stub satisfying graph construction — no API key needed."""
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
# merge_agent_outputs
# ===========================================================================

_MERGE_INPUT = json.dumps(
    {
        "ClusteringAgent": {"n_clusters": 3, "silhouette": 0.71},
        "AutoForecastAgent": {"best_model": "AutoARIMA", "rmse": 142.3},
    }
)


def test_merge_valid_input():
    from ai_data_science_team.tools.strategic import merge_agent_outputs

    text, artifact = merge_agent_outputs.func(outputs_json=_MERGE_INPUT)
    assert artifact["valid"] is True
    assert artifact["agent_count"] == 2
    assert artifact["total_keys"] == 4


def test_merge_keys_prefixed_with_agent_name():
    from ai_data_science_team.tools.strategic import merge_agent_outputs

    _, artifact = merge_agent_outputs.func(outputs_json=_MERGE_INPUT)
    merged = artifact["merged"]
    assert "ClusteringAgent.n_clusters" in merged
    assert "AutoForecastAgent.rmse" in merged


def test_merge_invalid_json():
    from ai_data_science_team.tools.strategic import merge_agent_outputs

    text, artifact = merge_agent_outputs.func(outputs_json="not-json{")
    assert artifact["valid"] is False
    assert "❌" in text


def test_merge_empty_dict():
    from ai_data_science_team.tools.strategic import merge_agent_outputs

    _, artifact = merge_agent_outputs.func(outputs_json="{}")
    assert artifact["agent_count"] == 0
    assert artifact["total_keys"] == 0


# ===========================================================================
# extract_key_metrics
# ===========================================================================

_MERGED_FLAT = json.dumps(
    {
        "ClusteringAgent.silhouette": 0.71,
        "ClusteringAgent.n_clusters": 3,
        "AutoForecastAgent.rmse": 142.3,
        "AutoForecastAgent.best_model": "AutoARIMA",
    }
)


def test_extract_filters_by_keyword():
    from ai_data_science_team.tools.strategic import extract_key_metrics

    _, artifact = extract_key_metrics.func(merged_json=_MERGED_FLAT, metric_keys="silhouette,rmse")
    assert artifact["found"] == 2
    assert any("silhouette" in k for k in artifact["metrics"])
    assert any("rmse" in k for k in artifact["metrics"])


def test_extract_empty_filter_returns_all():
    from ai_data_science_team.tools.strategic import extract_key_metrics

    _, artifact = extract_key_metrics.func(merged_json=_MERGED_FLAT, metric_keys="")
    assert artifact["found"] == 4


def test_extract_invalid_json():
    from ai_data_science_team.tools.strategic import extract_key_metrics

    text, artifact = extract_key_metrics.func(merged_json="INVALID", metric_keys="rmse")
    assert artifact["valid"] is False


# ===========================================================================
# compare_results
# ===========================================================================

_BASELINE = json.dumps({"accuracy": 0.80, "rmse": 200.0, "loss": 0.5})
_CURRENT = json.dumps({"accuracy": 0.85, "rmse": 160.0, "loss": 0.4})


def test_compare_improvements_detected():
    from ai_data_science_team.tools.strategic import compare_results

    _, artifact = compare_results.func(baseline_json=_BASELINE, current_json=_CURRENT)
    assert "accuracy" in artifact["improvements"]
    assert "rmse" in artifact["improvements"]
    assert "loss" in artifact["improvements"]


def test_compare_delta_values_correct():
    from ai_data_science_team.tools.strategic import compare_results

    _, artifact = compare_results.func(baseline_json=_BASELINE, current_json=_CURRENT)
    assert artifact["deltas"]["accuracy"]["delta"] == pytest.approx(0.05, abs=1e-6)
    assert artifact["deltas"]["rmse"]["delta"] == pytest.approx(-40.0, abs=1e-6)


def test_compare_regressions_detected():
    from ai_data_science_team.tools.strategic import compare_results

    worse = json.dumps({"accuracy": 0.70, "rmse": 250.0})
    _, artifact = compare_results.func(baseline_json=_BASELINE, current_json=worse)
    assert "accuracy" in artifact["regressions"]
    assert "rmse" in artifact["regressions"]


def test_compare_invalid_json():
    from ai_data_science_team.tools.strategic import compare_results

    text, artifact = compare_results.func(baseline_json="BAD", current_json="{}")
    assert artifact["valid"] is False


# ===========================================================================
# rank_findings
# ===========================================================================

_FINDINGS = json.dumps(
    [
        {"description": "Churn spike in Q3", "impact": 0.9, "confidence": 0.8},
        {"description": "Revenue opportunity", "impact": 0.6, "confidence": 0.7},
        {"description": "Minor UI bug", "impact": 0.1, "confidence": 0.95},
    ]
)


def test_rank_descending_by_impact():
    from ai_data_science_team.tools.strategic import rank_findings

    _, artifact = rank_findings.func(findings_json=_FINDINGS, sort_by="impact", descending=True)
    ranked = artifact["ranked"]
    assert ranked[0]["description"] == "Churn spike in Q3"
    assert ranked[-1]["description"] == "Minor UI bug"


def test_rank_top_n_limits():
    from ai_data_science_team.tools.strategic import rank_findings

    _, artifact = rank_findings.func(findings_json=_FINDINGS, top_n=2)
    assert len(artifact["ranked"]) == 2


def test_rank_total_preserved():
    from ai_data_science_team.tools.strategic import rank_findings

    _, artifact = rank_findings.func(findings_json=_FINDINGS)
    assert artifact["total"] == 3


def test_rank_invalid_json():
    from ai_data_science_team.tools.strategic import rank_findings

    text, artifact = rank_findings.func(findings_json="[invalid")
    assert artifact["valid"] is False


# ===========================================================================
# build_context_profile
# ===========================================================================


def test_build_context_profile_fields():
    from ai_data_science_team.tools.strategic import build_context_profile

    _, artifact = build_context_profile.func(
        company_name="Acme Corp",
        industry="e-commerce",
        goal="reduce churn by 20%",
        time_horizon="medium-term",
        kpis="churn_rate,CLV,NPS",
        audience="executive",
    )
    assert artifact["company_name"] == "Acme Corp"
    assert artifact["industry"] == "e-commerce"
    assert "churn_rate" in artifact["kpis"]
    assert artifact["audience"] == "executive"


def test_build_context_profile_kpi_list():
    from ai_data_science_team.tools.strategic import build_context_profile

    _, artifact = build_context_profile.func(kpis="ARR,MRR,CAC")
    assert len(artifact["kpis"]) == 3


def test_build_context_profile_text_contains_company():
    from ai_data_science_team.tools.strategic import build_context_profile

    text, _ = build_context_profile.func(company_name="TechCorp")
    assert "TechCorp" in text


# ===========================================================================
# generate_clarifying_questions
# ===========================================================================


def test_generate_questions_count():
    from ai_data_science_team.tools.strategic import generate_clarifying_questions

    _, artifact = generate_clarifying_questions.func(
        analysis_summary="Clustering of customer data", num_questions=4
    )
    assert artifact["count"] == 4
    assert len(artifact["questions"]) == 4


def test_generate_questions_focus_area():
    from ai_data_science_team.tools.strategic import generate_clarifying_questions

    _, artifact = generate_clarifying_questions.func(
        analysis_summary="Model deployment", focus_area="technical"
    )
    assert artifact["focus_area"] == "technical"


def test_generate_questions_capped_at_10():
    from ai_data_science_team.tools.strategic import generate_clarifying_questions

    _, artifact = generate_clarifying_questions.func(analysis_summary="test", num_questions=99)
    assert artifact["count"] <= 10


# ===========================================================================
# extract_business_entities
# ===========================================================================

_BUSINESS_TEXT = (
    "The Sales team wants to improve our NPS score and reduce churn rate by 15%. "
    "The Product team is launching a new e-commerce platform. "
    "Our target is to grow ARR by $5M in 2026."
)


def test_extract_kpi_entities():
    from ai_data_science_team.tools.strategic import extract_business_entities

    _, artifact = extract_business_entities.func(text=_BUSINESS_TEXT, entity_types="kpi,metric")
    assert artifact["total"] > 0
    assert "kpi" in artifact["entities"] or "metric" in artifact["entities"]


def test_extract_team_entities():
    from ai_data_science_team.tools.strategic import extract_business_entities

    _, artifact = extract_business_entities.func(text=_BUSINESS_TEXT, entity_types="team")
    assert "team" in artifact["entities"]


def test_extract_returns_requested_types():
    from ai_data_science_team.tools.strategic import extract_business_entities

    _, artifact = extract_business_entities.func(text=_BUSINESS_TEXT, entity_types="kpi")
    assert "kpi" in artifact["requested_types"]


# ===========================================================================
# generate_executive_summary
# ===========================================================================

_FINDINGS_RANKED = json.dumps(
    {
        "ranked": [
            {"description": "Churn spike in Q3", "impact": 0.9},
            {"description": "CLV up 12%", "impact": 0.7},
        ],
        "total": 2,
    }
)
_CONTEXT = json.dumps(
    {
        "company_name": "RetailCo",
        "industry": "retail",
        "goal": "reduce churn",
        "kpis": ["churn_rate", "CLV"],
        "audience": "executive",
        "time_horizon": "short-term",
    }
)


def test_executive_summary_contains_company():
    from ai_data_science_team.tools.strategic import generate_executive_summary

    text, artifact = generate_executive_summary.func(
        findings_json=_FINDINGS_RANKED, context_json=_CONTEXT, tone="executive"
    )
    assert "RetailCo" in artifact["summary"]


def test_executive_summary_word_count_bounded():
    from ai_data_science_team.tools.strategic import generate_executive_summary

    _, artifact = generate_executive_summary.func(
        findings_json=_FINDINGS_RANKED, context_json=_CONTEXT, max_words=50
    )
    assert artifact["word_count"] <= 60  # small tolerance for ellipsis


def test_executive_summary_artifact_keys():
    from ai_data_science_team.tools.strategic import generate_executive_summary

    _, artifact = generate_executive_summary.func(findings_json=_FINDINGS_RANKED)
    for key in ("summary", "tone", "word_count", "company", "n_findings"):
        assert key in artifact


# ===========================================================================
# generate_section
# ===========================================================================


def test_generate_section_findings():
    from ai_data_science_team.tools.strategic import generate_section

    text, artifact = generate_section.func(
        section_type="findings",
        data_json=json.dumps({"top_finding": "churn up 5%"}),
    )
    assert "Findings" in artifact["title"]
    assert "findings" in artifact["section_type"]
    assert "## " in artifact["content"]


def test_generate_section_custom_title():
    from ai_data_science_team.tools.strategic import generate_section

    _, artifact = generate_section.func(section_type="risks", title="Key Risks & Assumptions")
    assert artifact["title"] == "Key Risks & Assumptions"


def test_generate_section_artifact_keys():
    from ai_data_science_team.tools.strategic import generate_section

    _, artifact = generate_section.func(section_type="next_steps")
    for key in ("section_type", "title", "content", "tone", "data_keys"):
        assert key in artifact


def test_generate_section_unknown_type_falls_back():
    from ai_data_science_team.tools.strategic import generate_section

    _, artifact = generate_section.func(section_type="custom_section")
    assert artifact["section_type"] == "custom_section"
    assert len(artifact["content"]) > 0


# ===========================================================================
# format_report
# ===========================================================================

_SECTIONS = json.dumps(
    [
        "## Executive Summary\n\nGood results overall.",
        "## Findings\n\nChurn decreased by 5%.",
        "## Next Steps\n\n1. Monitor churn weekly.",
    ]
)


def test_format_report_assembles_sections():
    from ai_data_science_team.tools.strategic import format_report

    _, artifact = format_report.func(sections_json=_SECTIONS, title="Q1 2026 Report")
    assert artifact["section_count"] == 3
    assert "Q1 2026 Report" in artifact["report"]


def test_format_report_toc_present():
    from ai_data_science_team.tools.strategic import format_report

    _, artifact = format_report.func(
        sections_json=_SECTIONS, include_toc=True, format_type="markdown"
    )
    assert "Table of Contents" in artifact["report"]


def test_format_report_no_toc():
    from ai_data_science_team.tools.strategic import format_report

    _, artifact = format_report.func(sections_json=_SECTIONS, include_toc=False)
    assert "Table of Contents" not in artifact["report"]


def test_format_report_artifact_keys():
    from ai_data_science_team.tools.strategic import format_report

    _, artifact = format_report.func(sections_json=_SECTIONS)
    for key in ("report", "title", "section_count", "format_type"):
        assert key in artifact


# ===========================================================================
# generate_recommendations
# ===========================================================================


def test_recommendations_count():
    from ai_data_science_team.tools.strategic import generate_recommendations

    # _FINDINGS_RANKED has 2 ranked items; request 2 to match available data
    _, artifact = generate_recommendations.func(
        findings_json=_FINDINGS_RANKED,
        context_json=_CONTEXT,
        num_recommendations=2,
    )
    assert artifact["count"] == 2
    assert len(artifact["recommendations"]) == 2


def test_recommendations_have_required_keys():
    from ai_data_science_team.tools.strategic import generate_recommendations

    _, artifact = generate_recommendations.func(
        findings_json=_FINDINGS_RANKED, num_recommendations=2
    )
    for rec in artifact["recommendations"]:
        for key in ("rank", "action", "impact", "effort", "time_horizon"):
            assert key in rec


def test_recommendations_ranked_ascending():
    from ai_data_science_team.tools.strategic import generate_recommendations

    _, artifact = generate_recommendations.func(
        findings_json=_FINDINGS_RANKED, num_recommendations=2
    )
    ranks = [r["rank"] for r in artifact["recommendations"]]
    assert ranks == sorted(ranks)


# ===========================================================================
# design_ab_test
# ===========================================================================


def test_ab_test_feasible():
    from ai_data_science_team.tools.strategic import design_ab_test

    _, artifact = design_ab_test.func(
        hypothesis="Social proof increases checkout CVR",
        primary_metric="checkout_conversion_rate",
        expected_effect_pct=5.0,
        audience_size=100_000,
    )
    assert artifact["feasible"] is True
    assert "✅" in _  # text should contain feasible icon


def test_ab_test_infeasible_small_audience():
    from ai_data_science_team.tools.strategic import design_ab_test

    _, artifact = design_ab_test.func(
        hypothesis="Test",
        primary_metric="ctr",
        expected_effect_pct=1.0,  # tiny expected effect → huge n required
        audience_size=50,
    )
    assert artifact["feasible"] is False


def test_ab_test_plan_keys():
    from ai_data_science_team.tools.strategic import design_ab_test

    _, artifact = design_ab_test.func(hypothesis="H1", primary_metric="revenue")
    for key in (
        "hypothesis",
        "primary_metric",
        "n_per_variant",
        "n_total_required",
        "feasible",
        "success_criteria",
        "guardrail_metrics",
        "confidence_level",
    ):
        assert key in artifact


def test_ab_test_n_per_variant_positive():
    from ai_data_science_team.tools.strategic import design_ab_test

    _, artifact = design_ab_test.func(
        hypothesis="X", primary_metric="conversion", expected_effect_pct=10.0
    )
    assert artifact["n_per_variant"] > 0
    assert artifact["n_total_required"] == artifact["n_per_variant"] * 2


# ===========================================================================
# prioritize_actions
# ===========================================================================

_ACTIONS = json.dumps(
    [
        {"description": "Launch loyalty programme", "impact": 8, "confidence": 7, "ease": 5},
        {"description": "Fix checkout bug", "impact": 9, "confidence": 9, "ease": 9},
        {"description": "A/B test new homepage", "impact": 5, "confidence": 6, "ease": 7},
    ]
)

_RICE_ACTIONS = json.dumps(
    [
        {
            "description": "Email campaign",
            "reach": 50000,
            "impact": 2.0,
            "confidence": 80,
            "effort": 2,
        },
        {
            "description": "Homepage redesign",
            "reach": 200000,
            "impact": 1.0,
            "confidence": 60,
            "effort": 10,
        },
    ]
)


def test_ice_prioritization_first_is_highest():
    from ai_data_science_team.tools.strategic import prioritize_actions

    _, artifact = prioritize_actions.func(actions_json=_ACTIONS, framework="ice")
    assert artifact["valid"] is True
    assert artifact["prioritized"][0]["priority_rank"] == 1
    # Fix checkout bug has highest ICE (9*9*9 = 729)
    assert "Fix checkout bug" in artifact["prioritized"][0]["description"]


def test_ice_scores_present():
    from ai_data_science_team.tools.strategic import prioritize_actions

    _, artifact = prioritize_actions.func(actions_json=_ACTIONS, framework="ice")
    for a in artifact["prioritized"]:
        assert "ice_score" in a


def test_rice_prioritization():
    from ai_data_science_team.tools.strategic import prioritize_actions

    _, artifact = prioritize_actions.func(actions_json=_RICE_ACTIONS, framework="rice")
    assert artifact["valid"] is True
    for a in artifact["prioritized"]:
        assert "rice_score" in a


def test_prioritize_invalid_json():
    from ai_data_science_team.tools.strategic import prioritize_actions

    text, artifact = prioritize_actions.func(actions_json="[bad json")
    assert artifact["valid"] is False


# ===========================================================================
# Agent construction tests
# ===========================================================================


def test_results_synthesizer_instantiation():
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent

    agent = ResultsSynthesizerAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_ai_message")
    assert hasattr(agent, "get_artifacts")
    assert hasattr(agent, "get_tool_calls")


def test_results_synthesizer_nodes():
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent

    agent = ResultsSynthesizerAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)
    assert any("post" in n for n in node_names)


def test_results_synthesizer_state_before_invoke():
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent

    agent = ResultsSynthesizerAgent(model=_fake_llm())
    assert agent.get_ai_message() is None
    assert agent.get_artifacts() == {}
    assert agent.get_tool_calls() == []


def test_results_synthesizer_update_params_rebuilds():
    from ai_data_science_team.agents.strategic_agents import ResultsSynthesizerAgent

    agent = ResultsSynthesizerAgent(model=_fake_llm())
    original = agent._compiled_graph
    agent.update_params(system_prompt="New prompt.")
    assert agent._compiled_graph is not original


def test_contextual_knowledge_instantiation():
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent

    agent = ContextualKnowledgeAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")


def test_contextual_knowledge_nodes():
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent

    agent = ContextualKnowledgeAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)


def test_contextual_knowledge_state_before_invoke():
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent

    agent = ContextualKnowledgeAgent(model=_fake_llm())
    assert agent.get_ai_message() is None
    assert agent.get_artifacts() == {}


def test_contextual_knowledge_update_params():
    from ai_data_science_team.agents.strategic_agents import ContextualKnowledgeAgent

    agent = ContextualKnowledgeAgent(model=_fake_llm())
    original = agent._compiled_graph
    agent.update_params(system_prompt="Updated.")
    assert agent._compiled_graph is not original


def test_narrative_agent_instantiation():
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent

    agent = NarrativeAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "get_ai_message")


def test_narrative_agent_nodes():
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent

    agent = NarrativeAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("post" in n for n in node_names)


def test_narrative_agent_state_before_invoke():
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent

    agent = NarrativeAgent(model=_fake_llm())
    assert agent.get_artifacts() == {}
    assert agent.get_tool_calls() == []


def test_narrative_agent_update_params():
    from ai_data_science_team.agents.strategic_agents import NarrativeAgent

    agent = NarrativeAgent(model=_fake_llm())
    original = agent._compiled_graph
    agent.update_params(system_prompt="Custom narrative prompt.")
    assert agent._compiled_graph is not original


def test_recommendation_agent_instantiation():
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent

    agent = RecommendationAgent(model=_fake_llm())
    assert hasattr(agent, "invoke_agent")


def test_recommendation_agent_nodes():
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent

    agent = RecommendationAgent(model=_fake_llm())
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)
    assert any("post" in n for n in node_names)


def test_recommendation_agent_state_before_invoke():
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent

    agent = RecommendationAgent(model=_fake_llm())
    assert agent.get_ai_message() is None
    assert agent.get_artifacts() == {}


def test_recommendation_agent_update_params():
    from ai_data_science_team.agents.strategic_agents import RecommendationAgent

    agent = RecommendationAgent(model=_fake_llm())
    original = agent._compiled_graph
    agent.update_params(system_prompt="Another prompt.")
    assert agent._compiled_graph is not original


def test_all_four_agents_have_distinct_graphs():
    from ai_data_science_team.agents.strategic_agents import (
        ContextualKnowledgeAgent,
        NarrativeAgent,
        RecommendationAgent,
        ResultsSynthesizerAgent,
    )

    llm = _fake_llm()
    synth = ResultsSynthesizerAgent(model=llm)
    ctx = ContextualKnowledgeAgent(model=llm)
    narr = NarrativeAgent(model=llm)
    rec = RecommendationAgent(model=llm)

    graphs = [synth._compiled_graph, ctx._compiled_graph, narr._compiled_graph, rec._compiled_graph]
    # All four compiled graphs are distinct objects
    assert len({id(g) for g in graphs}) == 4
