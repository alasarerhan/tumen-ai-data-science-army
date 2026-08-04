"""GERÇEK model-driven balance_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.balance_agent import (
    apply_strategy_wrapped,
    balance_payload_wrapped,
    class_distribution_wrapped,
    class_weight_wrapped,
    estimate_strategy_impact_wrapped,
    is_imbalanced_wrapped,
    recommend_metrics_wrapped,
    select_strategy_wrapped,
    undersample_indices_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_class_distribution_real(llm_or_skip, llm_model):
    tool = class_distribution_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "class_distribution_wrapped tool'unu TEK çağrı ile çağır; y=['a','a','b'] ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_undersample_indices_real(llm_or_skip, llm_model):
    tool = undersample_indices_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "undersample_indices_wrapped tool'unu TEK çağrı ile çağır; y=['a','a','b','b'] ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_class_weight_real(llm_or_skip, llm_model):
    tool = class_weight_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "class_weight_wrapped tool'unu TEK çağrı ile çağır; y=['a','a','b'] ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_apply_strategy_real(llm_or_skip, llm_model):
    tool = apply_strategy_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "apply_strategy_wrapped tool'unu TEK çağrı ile çağır; y=['a','a','b'], strategy='class_weight' ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_is_imbalanced_stateful_skipped():
    assert hasattr(is_imbalanced_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_select_strategy_stateful_skipped():
    assert hasattr(select_strategy_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_estimate_strategy_impact_stateful_skipped():
    assert hasattr(estimate_strategy_impact_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_recommend_metrics_stateful_skipped():
    assert hasattr(recommend_metrics_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_balance_payload_stateful_skipped():
    assert hasattr(balance_payload_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
