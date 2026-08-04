"""GERÇEK test deep_learning_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/deep_learning_agent.py — 7 tool.

Strateji:
- PURE (model-driven): ``detect_device_wrapped``, ``build_*_wrapped``
  tool'ları model tarafından çağrılır.
- STATEFUL: ``train_mlp_classifier_wrapped`` ve ``train_lstm_forecaster_wrapped``
  np.ndarray alır; bu test'lerde pytest.skip yerine küçük numpy array'ler
  yaratılır ve **underlying tool** (``train_mlp_classifier``,
  ``train_lstm_forecaster``) doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.agents.deep_learning_agent import (
    build_lstm_classifier_wrapped,
    build_lstm_forecaster_wrapped,
    build_mlp_classifier_wrapped,
    build_mlp_regressor_wrapped,
    detect_device_wrapped,
)
from ai_data_science_team.tools.deep_learning import (
    train_lstm_forecaster,
    train_mlp_classifier,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: model-driven tool'lar
# ---------------------------------------------------------------------------

def test_detect_device_real(llm_or_skip, llm_model):
    tool = detect_device_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "detect_device_wrapped tool'unu TEK çağrı ile çağır; prefer='cpu' ver.",
        ),
        tool.name,
    )


def test_build_mlp_classifier_real(llm_or_skip, llm_model):
    tool = build_mlp_classifier_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_mlp_classifier_wrapped tool'unu TEK çağrı ile çağır; "
            "n_features=4, n_classes=2, hidden=[8], dropout=0.1 ver.",
        ),
        tool.name,
    )


def test_build_mlp_regressor_real(llm_or_skip, llm_model):
    tool = build_mlp_regressor_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_mlp_regressor_wrapped tool'unu TEK çağrı ile çağır; "
            "n_features=4, hidden=[8], dropout=0.1 ver.",
        ),
        tool.name,
    )


def test_build_lstm_forecaster_real(llm_or_skip, llm_model):
    tool = build_lstm_forecaster_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_lstm_forecaster_wrapped tool'unu TEK çağrı ile çağır; "
            "n_features=3, hidden=8, layers=1, horizon=2 ver.",
        ),
        tool.name,
    )


def test_build_lstm_classifier_real(llm_or_skip, llm_model):
    tool = build_lstm_classifier_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "build_lstm_classifier_wrapped tool'unu TEK çağrı ile çağır; "
            "n_features=3, n_classes=2, hidden=8, layers=1 ver.",
        ),
        tool.name,
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: np.ndarray → underlying tool.func() doğrudan çağrı
# ---------------------------------------------------------------------------

def test_train_mlp_classifier_real():
    """``train_mlp_classifier`` np.ndarray alır; küçük eğitim verisi ile test.

    underlying tool imzası: ``train_mlp_classifier(X, y, *, hidden=..., dropout=...,
    epochs=..., batch_size=..., lr=..., weight_decay=..., early_stopping_patience=...,
    val_split=..., seed=..., device=..., task_type=..., verbose=...) -> dict``.
    """
    rng = np.random.default_rng(0)
    X = rng.random((40, 4), dtype=np.float32)
    y = np.array([0, 1] * 20, dtype=np.int64)
    out = train_mlp_classifier(
        X, y, hidden=(8,), dropout=0.1, epochs=2,
        early_stopping_patience=1, seed=0, verbose=False,
    )
    assert "model" in out
    assert "loss_curve" in out
    assert out["n_epochs_run"] >= 1
    assert isinstance(out["metric_curve"], list)


def test_train_lstm_forecaster_real():
    """``train_lstm_forecaster`` 3-D X alır (samples, timesteps, features)."""
    rng = np.random.default_rng(0)
    X = rng.random((30, 3, 2), dtype=np.float32)
    y = rng.random(30, dtype=np.float32)
    out = train_lstm_forecaster(
        X, y, hidden=4, layers=1, horizon=1,
        epochs=2, verbose=False,
    )
    assert "model" in out
    assert "loss_curve" in out
    assert out["n_epochs_run"] >= 1
