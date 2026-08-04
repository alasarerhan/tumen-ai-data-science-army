"""GERÇEK model-driven responsible_ai_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.responsible_ai_agent import (
    build_dashboard_wrapped,
    compute_explainability_wrapped,
    compute_fairness_wrapped,
    dashboard_payload_wrapped,
    discover_error_slices_wrapped,
    suggest_mitigations_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_compute_fairness_real(llm_or_skip, llm_model):
    tool = compute_fairness_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "compute_fairness_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_compute_explainability_real(llm_or_skip, llm_model):
    tool = compute_explainability_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "compute_explainability_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_discover_error_slices_real(llm_or_skip, llm_model):
    tool = discover_error_slices_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "discover_error_slices_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_build_dashboard_real(llm_or_skip, llm_model):
    tool = build_dashboard_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_dashboard_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_suggest_mitigations_stateful_skipped():
    assert hasattr(suggest_mitigations_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_dashboard_payload_stateful_skipped():
    assert hasattr(dashboard_payload_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
