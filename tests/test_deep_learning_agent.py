"""deep_learning_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_deep_learning_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.deep_learning_agent import (
    AGENT_NAME,
    DEEP_LEARNING_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "detect_device_wrapped",
    "build_mlp_classifier_wrapped",
    "build_mlp_regressor_wrapped",
    "build_lstm_forecaster_wrapped",
    "build_lstm_classifier_wrapped",
    "train_mlp_classifier_wrapped",
    "train_lstm_forecaster_wrapped",
]


def test_constants():
    assert AGENT_NAME == "deep_learning_agent"
    assert NODE_TYPE == "model.train.deep"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in DEEP_LEARNING_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.deep_learning_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
