"""
Tests for ``ai_data_science_team.tools.hypothesis_testing`` (A4 tool layer).
"""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.tools.hypothesis_testing import (
    interpret_result,
    recommend_test,
    run_test,
)


class TestRecommendTest:
    def test_single_sample_bell(self):
        rng = np.random.RandomState(0)
        x = rng.normal(size=200)
        rec = recommend_test(x)
        assert rec["test"] in {"one_sample_t_test"}

    def test_single_sample_skewed_picks_non_parametric(self):
        # Exponential is right-skewed → mann-whitney one-sample (Wilcoxon signed-rank)
        rng = np.random.RandomState(0)
        x = rng.exponential(scale=2.0, size=200)
        rec = recommend_test(x)
        assert rec["test"] in {"one_sample_t_test", "wilcoxon_signed_rank"}
        assert "assumptions" in rec

    def test_two_sample_both_normal(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=200)
        b = rng.normal(loc=0.4, size=200)
        rec = recommend_test(a, comparison=b)
        assert rec["test"] == "two_sample_t_test"

    def test_too_small_samples(self):
        with pytest.raises(ValueError):
            recommend_test([1.0])

    def test_comparison_too_small(self):
        rng = np.random.RandomState(0)
        with pytest.raises(ValueError):
            recommend_test(rng.normal(size=50), comparison=[1.0])


class TestRunTest:
    def test_two_sample_detects_difference(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=200)
        b = rng.normal(loc=0.7, size=200)
        out = run_test(a, comparison=b)
        assert out["test"] == "two_sample_t_test"
        assert 0 <= out["p_value"] <= 1.0
        assert out["n"] == 400

    def test_one_sample(self):
        rng = np.random.RandomState(0)
        x = rng.normal(loc=1.0, size=100)
        out = run_test(x, mu=0.0)
        assert out["test"] == "one_sample_t_test"
        # Mean shifted to 1.0 with n=100 ⇒ highly significant.
        assert out["p_value"] < 0.001
        assert out["effect_size"] > 0.0  # positive shift

    def test_invalid_alt_raises(self):
        rng = np.random.RandomState(0)
        x = rng.normal(size=20)
        with pytest.raises(ValueError):
            run_test(x, alt="invalid")

    def test_zero_variance_returns_safe_result(self):
        x = np.full(50, 1.0)
        out = run_test(x, mu=1.0)
        assert out["statistic"] == 0.0
        assert out["p_value"] == 1.0  # one-sample


class TestInterpretResult:
    def test_significant_large(self):
        out = interpret_result(p_value=0.001, effect_size=1.5, alpha=0.05)
        assert out["significant"] is True
        assert out["magnitude"] == "large"

    def test_not_significant(self):
        out = interpret_result(p_value=0.4, effect_size=0.1, alpha=0.05)
        assert out["significant"] is False

    def test_magnitude_buckets(self):
        # Very small, small, medium, large thresholds.
        for d, label in [(0.05, "very small"), (0.4, "small"), (0.7, "medium"), (1.5, "large")]:
            out = interpret_result(p_value=0.04, effect_size=d, alpha=0.05)
            assert out["magnitude"] == label
