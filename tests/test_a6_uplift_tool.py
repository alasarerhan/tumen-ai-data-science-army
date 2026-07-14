"""Tests for A6 uplift tool layer."""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.tools.a6_uplift import (
    SEGMENTS,
    classify_segments,
    qini_curve,
    two_model_uplift,
)


def _synthetic(n=600):
    rng = np.random.RandomState(0)
    X = rng.normal(size=(n, 3))
    # Treatment effect depends on the first two covariates.
    score = X[:, 0] + 0.5 * X[:, 1]
    p = 1 / (1 + np.exp(-score))
    y = (rng.uniform(size=n) < p).astype(int)
    t = rng.binomial(1, 0.5, size=n)
    return X, t, y


class TestTwoModelUplift:
    def test_basic_shape(self):
        X, t, y = _synthetic()
        out = two_model_uplift(X, t, y)
        assert out["uplift_scores"].shape == (X.shape[0],)
        assert out["p_control"].shape == (X.shape[0],)
        assert out["p_treatment"].shape == (X.shape[0],)
        assert out["method"] == "t_learner"
        assert out["segments"] == SEGMENTS

    def test_invalid_dim_raises(self):
        X, t, y = _synthetic()
        with pytest.raises(ValueError):
            two_model_uplift(X.ravel(), t, y)

    def test_non_binary_treatment_raises(self):
        X, t, y = _synthetic()
        t = np.where(t == 0, 0, 2)
        with pytest.raises(ValueError):
            two_model_uplift(X, t, y)


class TestClassifySegments:
    def test_counts_add_up(self):
        X, t, y = _synthetic()
        out = two_model_uplift(X, t, y)
        seg = classify_segments(out["p_control"], out["p_treatment"])
        total = sum(int(s.sum()) for s in seg.values())
        assert total == X.shape[0]

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            classify_segments(np.array([0.1, 0.2]), np.array([0.1]))


class TestQiniCurve:
    def test_basic(self):
        X, t, y = _synthetic()
        out = two_model_uplift(X, t, y)
        qc = qini_curve(out["uplift_scores"], t, y, n_bins=10)
        assert len(qc["bins"]) == len(qc["cum_uplift"]) == 10
        assert qc["bins"][-1] == pytest.approx(1.0)
        assert -0.5 <= qc["qini_score"] <= 1.0

    def test_one_arm_only_returns_zero_curve(self):
        rng = np.random.RandomState(0)
        X = rng.normal(size=(50, 2))
        y = (rng.uniform(size=50) > 0.5).astype(int)
        t = np.zeros(50, dtype=int)  # all control
        scores = np.linspace(-1, 1, 50)
        out = qini_curve(scores, t, y)
        assert out["qini_score"] == 0.0
