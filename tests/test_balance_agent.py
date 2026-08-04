"""balance_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_balance_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.balance_agent import (
    AGENT_NAME,
    DATA_BALANCING_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "class_distribution_wrapped",
    "is_imbalanced_wrapped",
    "select_strategy_wrapped",
    "estimate_strategy_impact_wrapped",
    "recommend_metrics_wrapped",
    "undersample_indices_wrapped",
    "class_weight_wrapped",
    "apply_strategy_wrapped",
    "balance_payload_wrapped",
]


def test_constants():
    assert AGENT_NAME == "balance_agent"
    assert NODE_TYPE == "model.balance"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in DATA_BALANCING_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.balance_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
