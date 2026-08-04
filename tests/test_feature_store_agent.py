"""feature_store_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_feature_store_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.feature_store_agent import (
    AGENT_NAME,
    FEATURE_STORE_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "register_feature_wrapped",
    "search_features_wrapped",
    "version_sort_key_wrapped",
    "latest_version_wrapped",
    "check_consistency_wrapped",
    "probe_freshness_wrapped",
    "bulk_probe_freshness_wrapped",
    "attach_lineage_wrapped",
    "catalog_payload_wrapped",
]


def test_constants():
    assert AGENT_NAME == "feature_store_agent"
    assert NODE_TYPE == "feature.register"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in FEATURE_STORE_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.feature_store_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
