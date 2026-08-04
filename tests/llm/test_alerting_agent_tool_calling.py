"""GERÇEK model-driven alerting_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.alerting_agent import (
    acknowledge_incident_wrapped,
    channel_template_wrapped,
    define_rule_wrapped,
    evaluate_rule_wrapped,
    raise_incident_wrapped,
    resolve_incident_wrapped,
    route_to_channels_wrapped,
    summarise_wrapped,
    tick_escalation_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_channel_template_real(llm_or_skip, llm_model):
    tool = channel_template_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "channel_template_wrapped tool'unu TEK çağrı ile çağır; channel='slack', payload={'title':'Latency high','severity':'warning'} ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_define_rule_stateful_skipped():
    assert hasattr(define_rule_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_evaluate_rule_stateful_skipped():
    assert hasattr(evaluate_rule_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_raise_incident_stateful_skipped():
    assert hasattr(raise_incident_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_acknowledge_incident_stateful_skipped():
    assert hasattr(acknowledge_incident_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_resolve_incident_stateful_skipped():
    assert hasattr(resolve_incident_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_tick_escalation_stateful_skipped():
    assert hasattr(tick_escalation_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_route_to_channels_stateful_skipped():
    assert hasattr(route_to_channels_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_summarise_stateful_skipped():
    assert hasattr(summarise_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
