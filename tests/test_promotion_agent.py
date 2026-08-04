"""promotion_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_promotion_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.promotion_agent import (
    AGENT_NAME,
    MODEL_PROMOTION_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "register_version_wrapped",
    "validate_signature_wrapped",
    "evaluate_min_metrics_wrapped",
    "request_promotion_wrapped",
    "approve_wrapped",
    "demote_wrapped",
    "get_version_by_stage_wrapped",
    "mlflow_alias_sync_wrapped",
]


def test_constants():
    assert AGENT_NAME == "promotion_agent"
    assert NODE_TYPE == "deploy.promote"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in MODEL_PROMOTION_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.promotion_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
