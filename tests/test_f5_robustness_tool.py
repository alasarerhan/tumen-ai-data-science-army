"""Tests for ``ai_data_science_team.tools.f5_robustness`` (F5 tool layer)."""

from __future__ import annotations

import numpy as np
import pytest

import ai_data_science_team.tools.f5_robustness as f5


def _toy():
    rng = np.random.RandomState(0)
    X = rng.normal(size=(50, 4))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    return X, y


# A trivial "model" — predicts positive if x[:,0] > 0, else negative.
def _predict(X):
    return (X[:, 0] > 0).astype(int)


class TestGaussianNoise:
    def test_shape(self):
        X, _ = _toy()
        out = f5.add_gaussian_noise(X, sigma=0.1, rng=np.random.default_rng(0))
        assert out.shape == X.shape

    def test_changes_values(self):
        X, _ = _toy()
        out = f5.add_gaussian_noise(X, sigma=0.5, rng=np.random.default_rng(0))
        assert not np.allclose(out, X)

    def test_zero_sigma(self):
        X, _ = _toy()
        out = f5.add_gaussian_noise(X, sigma=0.0, rng=np.random.default_rng(0))
        assert np.allclose(out, X.astype(float))


class TestMaskFeatures:
    def test_mask_rate(self):
        rng = np.random.default_rng(0)
        X = np.ones((200, 5))
        out = f5.mask_features(X, mask_rate=0.5, fill_value=-1.0, rng=rng)
        # 200 * 5 cells = 1000 cells, 50 % mask ⇒ 500 cells.
        n_masked = int((out == -1.0).sum())
        assert n_masked == 500

    def test_columns_subset(self):
        X = np.ones((100, 3))
        out = f5.mask_features(X, mask_rate=1.0, columns=[0])
        assert (out[:, 0] == 0).all()
        assert (out[:, 1] == 1).all()
        assert (out[:, 2] == 1).all()


class TestScenarios:
    def test_default_scenarios_cover(self):
        s = f5.default_scenarios()
        names = {sc.name for sc in s}
        assert "clean" in names
        assert "edge_case_min_features" in names
        assert "edge_case_max_features" in names
        assert "noise_sigma_0.1" in names
        assert "mask_30pct" in names


class TestEvaluateRobustness:
    def test_clean_equals_baseline(self):
        X, y = _toy()
        res = f5.evaluate_robustness(
            "stub", _predict, X, y, replicates=3, seed=0,
        )
        # All clean scenarios at replicate 0 have delta == 0.
        clean_row = res.summary.loc["clean"]
        assert clean_row["delta_from_clean"] == pytest.approx(0.0)

    def test_replicate_count(self):
        X, y = _toy()
        res = f5.evaluate_robustness(
            "stub", _predict, X, y, replicates=5, seed=0,
        )
        assert res.matrix.shape[1] == 5
        assert res.metadata["replicates"] == 5

    def test_to_dict(self):
        X, y = _toy()
        res = f5.evaluate_robustness("stub", _predict, X, y, replicates=2)
        d = res.to_dict()
        assert "matrix" in d
        assert "summary" in d
        assert "metadata" in d

    def test_custom_scenarios(self):
        X, y = _toy()
        custom = [f5.Scenario("noop", lambda X, y: X)]
        res = f5.evaluate_robustness(
            "stub", _predict, X, y, scenarios=custom, replicates=1,
        )
        assert list(res.summary.index) == ["noop"]


class TestToolRegistry:
    def test_present(self):
        for x in ("f5_add_gaussian_noise", "f5_mask_features",
                  "f5_default_scenarios", "f5_evaluate_robustness"):
            assert x in f5.F5_ROBUSTNESS_TOOL_NAMES
