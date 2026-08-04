"""model_card_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_model_card_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.model_card_agent import (
    AGENT_NAME,
    MODEL_CARD_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "generate_card_wrapped",
    "update_section_wrapped",
    "render_html_wrapped",
    "render_pdf_wrapped",
    "get_card_wrapped",
    "list_cards_wrapped",
]


def test_constants():
    assert AGENT_NAME == "model_card_agent"
    assert NODE_TYPE == "model.card"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in MODEL_CARD_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.model_card_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
