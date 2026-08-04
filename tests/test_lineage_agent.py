"""lineage_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_lineage_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.lineage_agent import (
    AGENT_NAME,
    LINEAGE_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "add_node_wrapped",
    "add_edge_wrapped",
    "ancestors_wrapped",
    "descendants_wrapped",
    "render_graph_wrapped",
    "node_summary_wrapped",
]


def test_constants():
    assert AGENT_NAME == "lineage_agent"
    assert NODE_TYPE == "lineage.render"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in LINEAGE_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.lineage_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
