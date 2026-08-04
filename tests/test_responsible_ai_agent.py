"""responsible_ai_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_responsible_ai_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.responsible_ai_agent import (
    AGENT_NAME,
    NODE_TYPE,
    RESPONSIBLE_AI_TOOLS,
)

EXPECTED_WRAPPERS = [
    "compute_fairness_wrapped",
    "compute_explainability_wrapped",
    "discover_error_slices_wrapped",
    "suggest_mitigations_wrapped",
    "build_dashboard_wrapped",
    "dashboard_payload_wrapped",
]


def test_constants():
    assert AGENT_NAME == "responsible_ai_agent"
    assert NODE_TYPE == "model.responsible_audit"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in RESPONSIBLE_AI_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.responsible_ai_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
