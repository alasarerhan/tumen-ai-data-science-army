"""investigation_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_investigation_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.investigation_agent import (
    AGENT_NAME,
    INVESTIGATION_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "detect_change_wrapped",
    "isolate_dimension_wrapped",
    "quantify_contributors_wrapped",
    "narrate_wrapped",
    "investigate_wrapped",
]


def test_constants():
    assert AGENT_NAME == "investigation_agent"
    assert NODE_TYPE == "kpi.investigate"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in INVESTIGATION_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.investigation_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
