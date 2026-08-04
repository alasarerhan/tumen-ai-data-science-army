"""GERÇEK model-driven deep_learning_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.deep_learning_agent import (
    build_lstm_classifier_wrapped,
    build_lstm_forecaster_wrapped,
    build_mlp_classifier_wrapped,
    build_mlp_regressor_wrapped,
    detect_device_wrapped,
    train_lstm_forecaster_wrapped,
    train_mlp_classifier_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_detect_device_real(llm_or_skip, llm_model):
    tool = detect_device_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "detect_device_wrapped tool'unu TEK çağrı ile çağır; prefer='cpu' ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_build_mlp_classifier_real(llm_or_skip, llm_model):
    tool = build_mlp_classifier_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_mlp_classifier_wrapped tool'unu TEK çağrı ile çağır; n_features=4, n_classes=2, hidden=[8], dropout=0.1 ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_build_mlp_regressor_real(llm_or_skip, llm_model):
    tool = build_mlp_regressor_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_mlp_regressor_wrapped tool'unu TEK çağrı ile çağır; n_features=4, hidden=[8], dropout=0.1 ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_build_lstm_forecaster_real(llm_or_skip, llm_model):
    tool = build_lstm_forecaster_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_lstm_forecaster_wrapped tool'unu TEK çağrı ile çağır; n_features=3, hidden=8, layers=1, horizon=2 ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_build_lstm_classifier_real(llm_or_skip, llm_model):
    tool = build_lstm_classifier_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_lstm_classifier_wrapped tool'unu TEK çağrı ile çağır; n_features=3, n_classes=2, hidden=8, layers=1 ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_train_mlp_classifier_stateful_skipped():
    assert hasattr(train_mlp_classifier_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_train_lstm_forecaster_stateful_skipped():
    assert hasattr(train_lstm_forecaster_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
