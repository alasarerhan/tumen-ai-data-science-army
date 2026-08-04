"""shadow_canary_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_shadow_canary_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.shadow_canary_agent import (
    AGENT_NAME,
    NODE_TYPE,
    SHADOW_CANARY_TOOLS,
)

EXPECTED_WRAPPERS = [
    "start_deployment_wrapped",
    "record_live_sample_wrapped",
    "evaluate_rollback_wrapped",
    "mark_status_wrapped",
    "summarise_deployment_wrapped",
    "list_deployments_wrapped",
]


def test_constants():
    assert AGENT_NAME == "shadow_canary_agent"
    assert NODE_TYPE == "deploy.shadow"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in SHADOW_CANARY_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.shadow_canary_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
