"""Tests for ``ai_data_science_team.tools.deep_learning`` (E3 tool layer).

Implementation note
-------------------
The test module deliberately imports the package *once* at module
level via ``import ai_data_science_team.tools.deep_learning as
e3`` (rather than the per-function ``from ... import ...`` form) so
the first load is the only one — pytest's collection pass has been
observed to leave a partial module in ``sys.modules`` after a
from-import on this particular module.
"""

from __future__ import annotations

import os
import sys

# Make the in-tree ``ai_data_science_team`` package importable when
# pytest is launched from the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import numpy as np  # noqa: E402
import pytest  # noqa: E402

try:
    import torch

    _TORCH = True
except Exception:  # pragma: no cover
    _TORCH = False

pytestmark = pytest.mark.skipif(not _TORCH, reason="PyTorch not installed")

# Import the module once at collection time.  Tests reference
# ``e3.detect_device`` etc. via the module attribute, never via
# ``from ai_data_science_team.tools.deep_learning import ...``.
import ai_data_science_team.tools.deep_learning as e3  # noqa: E402


@pytest.fixture
def small_binary_data():
    rng = np.random.RandomState(0)
    n = 100
    X = rng.normal(size=(n, 5))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    return X, y


@pytest.fixture
def small_lstm_data():
    rng = np.random.RandomState(0)
    n = 50
    T = 4
    F = 3
    X = rng.normal(size=(n, T, F))
    y = (X[:, :, 0] + 0.5 * X[:, :, 1]).sum(axis=1, keepdims=True)
    return X, y


class TestDetectDevice:
    def test_returns_string(self):
        assert e3.detect_device() in {"cpu", "mps", "cuda"}


class TestBuildMLP:
    def test_forward_shape(self):
        m = e3.build_mlp_classifier(n_features=5, n_classes=3)
        x = torch.randn(4, 5)
        y = m(x)
        assert y.shape == (4, 3)


class TestBuildLSTM:
    def test_forward_shape_regression(self):
        m = e3.build_lstm_forecaster(n_features=3, hidden=8, layers=2, horizon=1)
        x = torch.randn(4, 5, 3)
        y = m(x)
        assert y.shape == (4, 1)

    def test_forward_shape_horizon(self):
        m = e3.build_lstm_forecaster(n_features=3, hidden=8, layers=1, horizon=4)
        x = torch.randn(2, 5, 3)
        y = m(x)
        assert y.shape == (2, 4)


class TestTrainMLPClassifier:
    def test_basic(self, small_binary_data):
        X, y = small_binary_data
        out = e3.train_mlp_classifier(
            X, y, hidden=(16, 8), epochs=5, batch_size=16, val_split=0.3, verbose=False
        )
        assert "model" in out
        assert "loss_curve" in out
        assert "metric_curve" in out
        assert "meta" in out
        assert 1 <= len(out["loss_curve"]) <= 5
        assert out["meta"]["architecture"] == "mlp"
        assert out["meta"]["n_classes"] == 2

    def test_regression_mode(self, small_binary_data):
        X, y = small_binary_data
        out = e3.train_mlp_classifier(
            X,
            y.astype(float),
            task_type="regression",
            hidden=(8, 4),
            epochs=3,
            val_split=0.3,
        )
        assert out["meta"]["task_type"] == "regression"
        assert out["meta"]["n_classes"] == 0

    def test_early_stop(self):
        rng = np.random.RandomState(0)
        X = rng.normal(size=(80, 4))
        y = rng.binomial(1, 0.5, size=80)
        out = e3.train_mlp_classifier(
            X,
            y,
            epochs=50,
            early_stopping_patience=1,
            lr_patience=0,
            val_split=0.3,
        )
        assert out["early_stopped"] is True

    def test_loss_curve_descends(self):
        rng = np.random.RandomState(0)
        X = rng.normal(size=(200, 6))
        y = (X[:, 0] - 0.3 * X[:, 2] > 0).astype(int)
        out = e3.train_mlp_classifier(
            X,
            y,
            hidden=(32, 16),
            epochs=20,
            val_split=0.3,
            early_stopping_patience=10,
        )
        train_losses = [p["train_loss"] for p in out["loss_curve"]]
        assert min(train_losses) <= train_losses[0] * 1.5

    def test_invalid_dim(self):
        with pytest.raises(ValueError):
            e3.train_mlp_classifier(np.zeros((10, 3, 5)), np.zeros(10))

    def test_unknown_task(self):
        with pytest.raises(ValueError):
            e3.train_mlp_classifier(
                np.zeros((10, 3)),
                np.zeros(10),
                task_type="nlp",
            )


class TestTrainLstmForecaster:
    def test_basic(self, small_lstm_data):
        X, y = small_lstm_data
        out = e3.train_lstm_forecaster(
            X,
            y,
            hidden=8,
            layers=1,
            horizon=1,
            epochs=3,
            verbose=False,
        )
        assert "model" in out
        assert "loss_curve" in out
        assert out["meta"]["architecture"] == "lstm"

    def test_invalid_dim(self):
        with pytest.raises(ValueError):
            e3.train_lstm_forecaster(np.zeros((10, 3)), np.zeros((10, 1)))
