"""alerting_agent modül yüzeyi testleri (LLM-free, gerçek nesneler).

Tool davranışı ``tests/llm/test_alerting_agent_tool_calling.py`` altında gerçek
model çağrılarıyla doğrulanır. Bu dosya yalnız sabitler ve StructuredTool
export sözleşmesini denetler; mock/stub/fake içermez.
"""

from __future__ import annotations

import sys

from ai_data_science_team.agents.alerting_agent import (
    AGENT_NAME,
    ALERTING_TOOLS,
    NODE_TYPE,
)

EXPECTED_WRAPPERS = [
    "define_rule_wrapped",
    "evaluate_rule_wrapped",
    "raise_incident_wrapped",
    "acknowledge_incident_wrapped",
    "resolve_incident_wrapped",
    "tick_escalation_wrapped",
    "route_to_channels_wrapped",
    "channel_template_wrapped",
    "summarise_wrapped",
]


def test_constants():
    assert AGENT_NAME == "alerting_agent"
    assert NODE_TYPE == "incident.raise"


def test_tool_registry_matches_expected_exports():
    assert [tool.name for tool in ALERTING_TOOLS] == EXPECTED_WRAPPERS


def test_all_wrapper_names_follow_convention():
    assert all(name.endswith("_wrapped") for name in EXPECTED_WRAPPERS)


def test_all_individual_tools_exported():
    module = sys.modules["ai_data_science_team.agents.alerting_agent"]
    for wrapper_name in EXPECTED_WRAPPERS:
        wrapper = getattr(module, wrapper_name)
        assert hasattr(wrapper, "name")
        assert hasattr(wrapper, "invoke")
        assert hasattr(wrapper, "func")
