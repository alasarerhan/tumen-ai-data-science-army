"""GERÇEK model-driven promotion_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.promotion_agent import (
    approve_wrapped,
    demote_wrapped,
    evaluate_min_metrics_wrapped,
    get_version_by_stage_wrapped,
    mlflow_alias_sync_wrapped,
    register_version_wrapped,
    request_promotion_wrapped,
    validate_signature_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_register_version_real(llm_or_skip, llm_model):
    tool = register_version_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "register_version_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo', version='1.0.0' ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_evaluate_min_metrics_real(llm_or_skip, llm_model):
    tool = evaluate_min_metrics_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "evaluate_min_metrics_wrapped tool'unu TEK çağrı ile çağır; metrics={'accuracy':0.91}, required={'accuracy':0.90} ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_mlflow_alias_sync_real(llm_or_skip, llm_model):
    tool = mlflow_alias_sync_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "mlflow_alias_sync_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo', version='1.0.0', alias='champion', registry_uri=None ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_validate_signature_stateful_skipped():
    assert hasattr(validate_signature_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_request_promotion_stateful_skipped():
    assert hasattr(request_promotion_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_approve_stateful_skipped():
    assert hasattr(approve_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_demote_stateful_skipped():
    assert hasattr(demote_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_get_version_by_stage_stateful_skipped():
    assert hasattr(get_version_by_stage_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
