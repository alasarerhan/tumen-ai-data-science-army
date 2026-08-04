"""GERÇEK model-driven retrain_orchestrator_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.retrain_orchestrator_agent import (
    build_audit_trail_wrapped,
    build_policy_wrapped,
    decide_action_wrapped,
    event_to_dict_wrapped,
    record_event_wrapped,
    simulate_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_build_policy_real(llm_or_skip, llm_model):
    tool = build_policy_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            (
                "build_policy_wrapped tool'unu TEK çağrı ile çağır; "
                "spec={'name':'drift','metric':'psi','threshold':0.2} ver."
            ),
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_decide_action_stateful_skipped():
    assert hasattr(decide_action_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_simulate_stateful_skipped():
    assert hasattr(simulate_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_record_event_stateful_skipped():
    assert hasattr(record_event_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_event_to_dict_stateful_skipped():
    assert hasattr(event_to_dict_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_build_audit_trail_stateful_skipped():
    assert hasattr(build_audit_trail_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
