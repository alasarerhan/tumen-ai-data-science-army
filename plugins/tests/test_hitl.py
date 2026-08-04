"""Tests for M17 — Human-in-the-Loop (HITL) tools and ApprovalGateAgent.

Tool tests call ``.func()`` directly (no LLM required).
Agent construction tests use a deterministic FakeChatModel stub.
"""

from __future__ import annotations

import json

# ===========================================================================
# Helpers
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


def _reset_hitl_stores():
    """Reset module-level in-memory stores between tests."""
    import ai_data_science_team.tools.hitl as _h

    _h._reset_stores()


# ===========================================================================
# create_approval_request
# ===========================================================================


def test_create_request_returns_tuple():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    result = create_approval_request.func(
        step_name="feature_engineering",
        description="One-hot encode all categoricals",
        data_summary="10 000 rows × 25 cols",
        risk_level="high",
        agent_name="FeatureEngineeringAgent",
    )
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_create_request_status_is_pending():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    _, artifact = create_approval_request.func(
        step_name="data_cleaning",
        description="Remove duplicate rows",
    )
    assert artifact["status"] == "pending"


def test_create_request_has_request_id():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    _, artifact = create_approval_request.func(
        step_name="clustering",
        description="Cluster customers into 5 segments",
    )
    assert "request_id" in artifact
    assert len(artifact["request_id"]) > 0


def test_create_request_stores_in_memory():
    _reset_hitl_stores()
    import ai_data_science_team.tools.hitl as _h
    from ai_data_science_team.tools.hitl import create_approval_request

    _, artifact = create_approval_request.func(
        step_name="model_training",
        description="Train XGBoost model",
    )
    request_id = artifact["request_id"]
    assert request_id in _h._APPROVAL_STORE


def test_create_request_risk_level_normalised():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    _, artifact = create_approval_request.func(
        step_name="test",
        description="test",
        risk_level="INVALID_RISK",
    )
    assert artifact["risk_level"] == "medium"


def test_create_request_valid_risk_levels():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    for risk in ("low", "medium", "high"):
        _, artifact = create_approval_request.func(
            step_name=f"step_{risk}",
            description="test",
            risk_level=risk,
        )
        assert artifact["risk_level"] == risk


def test_create_request_content_has_id_and_step():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    content, artifact = create_approval_request.func(
        step_name="wrangling", description="Pivot and merge tables"
    )
    assert artifact["request_id"] in content
    assert "wrangling" in content


def test_create_request_decision_fields_empty():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    _, artifact = create_approval_request.func(
        step_name="eda", description="Exploratory data analysis"
    )
    assert artifact["decision"] is None
    assert artifact["decided_by"] is None
    assert artifact["decided_at"] is None


# ===========================================================================
# format_approval_notification
# ===========================================================================


def _make_request_json(**kwargs):
    """Helper: build a minimal approval-request JSON string."""
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request

    _, artifact = create_approval_request.func(
        step_name=kwargs.get("step_name", "test_step"),
        description=kwargs.get("description", "A test step"),
        risk_level=kwargs.get("risk_level", "medium"),
        agent_name=kwargs.get("agent_name", "TestAgent"),
    )
    return json.dumps(artifact)


def test_format_notification_returns_markdown():
    from ai_data_science_team.tools.hitl import format_approval_notification

    content, artifact = format_approval_notification.func(
        request_json=_make_request_json(),
        channel="ui",
        urgency="normal",
    )
    assert "Approval Required" in content
    assert "notification_markdown" in artifact


def test_format_notification_invalid_json():
    from ai_data_science_team.tools.hitl import format_approval_notification

    content, artifact = format_approval_notification.func(
        request_json="not-json{[",
    )
    assert "ERROR" in content
    assert artifact["error"] == "invalid_json"


def test_format_notification_risk_icon():
    from ai_data_science_team.tools.hitl import format_approval_notification

    content, _ = format_approval_notification.func(
        request_json=_make_request_json(risk_level="high"),
        urgency="high",
    )
    # High urgency → 🔴 icon
    assert "🔴" in content


def test_format_notification_artifact_keys():
    from ai_data_science_team.tools.hitl import format_approval_notification

    _, artifact = format_approval_notification.func(
        request_json=_make_request_json(),
    )
    for key in (
        "notification_markdown",
        "request_id",
        "channel",
        "urgency",
        "risk_level",
        "step_name",
    ):
        assert key in artifact


def test_format_notification_contains_step_name():
    from ai_data_science_team.tools.hitl import format_approval_notification

    content, _ = format_approval_notification.func(
        request_json=_make_request_json(step_name="my_approval_step"),
    )
    assert "my_approval_step" in content


def test_format_notification_action_required_present():
    from ai_data_science_team.tools.hitl import format_approval_notification

    content, _ = format_approval_notification.func(
        request_json=_make_request_json(),
    )
    assert "Action Required" in content or "yes" in content.lower()


# ===========================================================================
# check_approval_status
# ===========================================================================


def test_check_status_pending():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import check_approval_status, create_approval_request

    _, req = create_approval_request.func(
        step_name="status_test", description="Check pending status"
    )
    content, artifact = check_approval_status.func(request_id=req["request_id"])
    assert artifact["status"] == "pending"
    assert artifact["request_id"] == req["request_id"]


def test_check_status_not_found():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import check_approval_status

    content, artifact = check_approval_status.func(request_id="nonexistent123")
    assert artifact["status"] == "not_found"
    assert "not found" in content.lower() or "not_found" in artifact["status"]


def test_check_status_artifact_keys():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import check_approval_status, create_approval_request

    _, req = create_approval_request.func(step_name="keys_test", description="Test keys")
    _, artifact = check_approval_status.func(request_id=req["request_id"])
    for key in ("request_id", "status", "step_name", "decision", "decision_reason"):
        assert key in artifact


def test_check_status_content_has_step_name():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import check_approval_status, create_approval_request

    _, req = create_approval_request.func(
        step_name="unique_step_xyz", description="For content test"
    )
    content, _ = check_approval_status.func(request_id=req["request_id"])
    assert "unique_step_xyz" in content


# ===========================================================================
# log_approval_decision
# ===========================================================================


def test_log_decision_approved():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import (
        check_approval_status,
        create_approval_request,
        log_approval_decision,
    )

    _, req = create_approval_request.func(step_name="approve_me", description="Approve this step")
    rid = req["request_id"]

    content, artifact = log_approval_decision.func(
        request_id=rid, decision="approved", reason="Looks good", modifier="data_scientist"
    )
    assert artifact["decision"] == "approved"
    assert artifact["modifier"] == "data_scientist"

    # Verify store was updated
    _, status_artifact = check_approval_status.func(request_id=rid)
    assert status_artifact["status"] == "approved"


def test_log_decision_rejected():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request, log_approval_decision

    _, req = create_approval_request.func(step_name="reject_step", description="Risky step")
    rid = req["request_id"]

    _, artifact = log_approval_decision.func(
        request_id=rid, decision="rejected", reason="Too risky"
    )
    assert artifact["decision"] == "rejected"


def test_log_decision_modified():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request, log_approval_decision

    _, req = create_approval_request.func(step_name="modify_step", description="Needs changes")
    rid = req["request_id"]

    _, artifact = log_approval_decision.func(
        request_id=rid, decision="modified", reason="Please use fewer clusters"
    )
    assert artifact["decision"] == "modified"
    assert "fewer clusters" in artifact["reason"]


def test_log_decision_normalises_unknown():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request, log_approval_decision

    _, req = create_approval_request.func(step_name="norm_test", description="Test norm")
    _, artifact = log_approval_decision.func(request_id=req["request_id"], decision="UNKNOWN_VALUE")
    assert artifact["decision"] == "modified"


def test_log_decision_added_to_decision_log():
    _reset_hitl_stores()
    import ai_data_science_team.tools.hitl as _h
    from ai_data_science_team.tools.hitl import create_approval_request, log_approval_decision

    _, req = create_approval_request.func(step_name="log_test", description="For log test")
    log_approval_decision.func(request_id=req["request_id"], decision="approved")

    assert len(_h._DECISION_LOG) == 1
    assert _h._DECISION_LOG[0]["decision"] == "approved"


def test_log_decision_content_has_request_id():
    _reset_hitl_stores()
    from ai_data_science_team.tools.hitl import create_approval_request, log_approval_decision

    _, req = create_approval_request.func(step_name="content_id_test", description="Test")
    rid = req["request_id"]
    content, _ = log_approval_decision.func(request_id=rid, decision="approved")
    assert rid in content


def test_log_decision_nonexistent_request_still_records():
    _reset_hitl_stores()
    import ai_data_science_team.tools.hitl as _h
    from ai_data_science_team.tools.hitl import log_approval_decision

    log_approval_decision.func(
        request_id="fake-id-999", decision="approved", reason="No store entry"
    )
    # Decision log should still receive the entry
    assert any(e["request_id"] == "fake-id-999" for e in _h._DECISION_LOG)


# ===========================================================================
# summarize_for_approval
# ===========================================================================


_AGENT_OUTPUT = json.dumps(
    {
        "n_clusters": 5,
        "silhouette_score": 0.72,
        "inertia": 1234.5,
        "best_model": "KMeans",
        "feature_importance": {"age": 0.4, "income": 0.35, "tenure": 0.25},
    }
)


def test_summarize_returns_tuple():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    result = summarize_for_approval.func(agent_output_json=_AGENT_OUTPUT)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_summarize_contains_markdown():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    content, _ = summarize_for_approval.func(agent_output_json=_AGENT_OUTPUT)
    assert "##" in content or "**" in content


def test_summarize_artifact_keys():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    _, artifact = summarize_for_approval.func(agent_output_json=_AGENT_OUTPUT)
    for key in ("summary_markdown", "total_keys", "summarised_keys", "focus_keys", "max_length"):
        assert key in artifact


def test_summarize_total_keys_correct():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    _, artifact = summarize_for_approval.func(agent_output_json=_AGENT_OUTPUT)
    assert artifact["total_keys"] == 5


def test_summarize_respects_focus_keys():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    content, artifact = summarize_for_approval.func(
        agent_output_json=_AGENT_OUTPUT,
        focus_keys="silhouette_score,best_model",
    )
    assert "silhouette_score" in artifact["focus_keys"]
    assert "best_model" in artifact["focus_keys"]
    # focus keys should appear early in summary
    assert "silhouette_score" in content


def test_summarize_invalid_json():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    content, artifact = summarize_for_approval.func(agent_output_json="{bad}")
    assert "ERROR" in content
    assert artifact["error"] == "invalid_json"


def test_summarize_respects_max_length():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    large_output = json.dumps({f"key_{i}": i * 1.5 for i in range(50)})
    _, artifact = summarize_for_approval.func(agent_output_json=large_output, max_length=100)
    # Should not summarise all 50 keys
    assert artifact["summarised_keys"] < 50


def test_summarize_empty_dict():
    from ai_data_science_team.tools.hitl import summarize_for_approval

    _, artifact = summarize_for_approval.func(agent_output_json="{}")
    assert artifact["total_keys"] == 0


# ===========================================================================
# ApprovalGateAgent — construction tests
# ===========================================================================


def test_approval_gate_agent_instantiation_no_hitl():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    assert hasattr(agent, "invoke_agent")
    assert hasattr(agent, "resume_agent")
    assert hasattr(agent, "get_ai_message")
    assert hasattr(agent, "get_artifacts")
    assert hasattr(agent, "get_tool_calls")
    assert hasattr(agent, "get_pending_approval")


def test_approval_gate_agent_instantiation_with_hitl():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=True)
    # Should auto-create MemorySaver
    assert agent._params["checkpointer"] is not None


def test_approval_gate_agent_custom_checkpointer():
    from langgraph.checkpoint.memory import MemorySaver

    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    cp = MemorySaver()
    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=True, checkpointer=cp)
    assert agent._params["checkpointer"] is cp


def test_approval_gate_nodes_no_hitl():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    node_names = list(agent.nodes.keys())
    assert any("prepare" in n for n in node_names)
    assert any("react" in n for n in node_names)
    assert any("post" in n for n in node_names)
    # No human_review node when HITL disabled
    assert not any("human_review" in n for n in node_names)


def test_approval_gate_nodes_with_hitl():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=True)
    node_names = list(agent.nodes.keys())
    assert any("human_review" in n for n in node_names)


def test_approval_gate_state_before_invoke():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    assert agent.get_ai_message() is None
    assert agent.get_artifacts() == {}
    assert agent.get_tool_calls() == []


def test_approval_gate_update_params_rebuilds():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    original = agent._compiled_graph
    agent.update_params(system_prompt="Updated system prompt.")
    assert agent._compiled_graph is not original


def test_approval_gate_update_params_toggle_hitl():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    assert not any("human_review" in n for n in agent.nodes.keys())

    agent.update_params(human_in_the_loop=True)
    assert any("human_review" in n for n in agent.nodes.keys())


def test_approval_gate_default_tools_count():
    from ai_data_science_team.agents.hitl_agent import _HITL_TOOLS, ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    assert len(agent._params["tools"]) == len(_HITL_TOOLS)
    assert len(_HITL_TOOLS) == 5


def test_approval_gate_custom_system_prompt():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    custom_prompt = "Custom HITL system prompt."
    agent = ApprovalGateAgent(
        model=_fake_llm(),
        human_in_the_loop=False,
        system_prompt=custom_prompt,
    )
    assert agent._params["system_prompt"] == custom_prompt


def test_approval_gate_custom_tools():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent
    from ai_data_science_team.tools.hitl import create_approval_request

    agent = ApprovalGateAgent(
        model=_fake_llm(),
        human_in_the_loop=False,
        tools=[create_approval_request],
    )
    assert len(agent._params["tools"]) == 1


def test_approval_gate_get_pending_approval_no_config():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    assert agent.get_pending_approval() is None


def test_approval_gate_graph_name():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    agent = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    assert "ApprovalGate" in (agent._compiled_graph.name or "")


def test_approval_gate_two_instances_distinct_graphs():
    from ai_data_science_team.agents.hitl_agent import ApprovalGateAgent

    a1 = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=False)
    a2 = ApprovalGateAgent(model=_fake_llm(), human_in_the_loop=True)
    assert a1._compiled_graph is not a2._compiled_graph


# ===========================================================================
# Integration: reset_stores utility
# ===========================================================================


def test_reset_stores_clears_approval_store():
    import ai_data_science_team.tools.hitl as _h
    from ai_data_science_team.tools.hitl import create_approval_request

    create_approval_request.func(step_name="temp", description="temp")
    assert len(_h._APPROVAL_STORE) > 0
    _h._reset_stores()
    assert len(_h._APPROVAL_STORE) == 0


def test_reset_stores_clears_decision_log():
    import ai_data_science_team.tools.hitl as _h
    from ai_data_science_team.tools.hitl import create_approval_request, log_approval_decision

    _, req = create_approval_request.func(step_name="tmp2", description="d")
    log_approval_decision.func(request_id=req["request_id"], decision="approved")
    assert len(_h._DECISION_LOG) > 0
    _h._reset_stores()
    assert len(_h._DECISION_LOG) == 0
