"""retrain_orchestrator_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_retrain_orchestrator_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.retrain_orchestrator_agent import (
    AGENT_NAME,
    NODE_TYPE,
    RETRAIN_ORCHESTRATOR_TOOLS,
)

EXPECTED_WRAPPERS = [
    "build_policy_wrapped",
    "decide_action_wrapped",
    "simulate_wrapped",
    "record_event_wrapped",
    "event_to_dict_wrapped",
    "build_audit_trail_wrapped",
]


def test_constants():
    assert AGENT_NAME == "retrain_orchestrator_agent"
    assert NODE_TYPE == "monitor.retrain"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in RETRAIN_ORCHESTRATOR_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.retrain_orchestrator_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
