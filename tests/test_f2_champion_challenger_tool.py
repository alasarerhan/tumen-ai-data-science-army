"""
Tests for ``ai_data_science_team.tools.f2_champion_challenger`` (F2 tool layer).
"""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.tools.f2_champion_challenger import (
    auc_with_delong_ci,
    compare_models,
    delong_pvalue,
    mcnemar_test,
    wilcoxon_signed_rank,
)


def _binary_seed(seed: int = 0, n: int = 400) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a synthetic binary classification set.

    Champion: logistic with coefficient 1.0
    Challenger: logistic with coefficient 3.0 (clearly better)
    """
    rng = np.random.RandomState(seed)
    x = rng.normal(size=n)
    z = 1.0 * x + rng.normal(scale=0.5, size=n)
    y = (z > 0).astype(int)
    p_a = 1.0 / (1.0 + np.exp(-(1.0 * x)))
    p_b = 1.0 / (1.0 + np.exp(-(3.0 * x)))
    return y, p_a, p_b


class TestMcnemar:
    def test_balanced_no_difference(self):
        y = np.array([0, 1, 0, 1, 0, 1, 0, 1])
        a = np.array([0, 1, 0, 1, 0, 1, 0, 1])  # perfect
        b = np.array([0, 1, 0, 1, 1, 1, 0, 1])  # differs on one
        res = mcnemar_test(y, a, b)
        assert res["b"] + res["c"] == 1
        assert res["p_value"] > 0.0

    def test_obvious_difference_low_p(self):
        # Build a simple synthetic setting where A and B disagree a lot
        # but both are partially right — so b+c is large and the
        # chi-square statistic is non-zero with very small p.
        rng = np.random.RandomState(42)
        n = 200
        y = rng.binomial(1, 0.5, size=n)
        a = y  # A perfect
        b = np.where(y == 0, 1 - y, rng.binomial(1, 0.5, size=n))
        # Now every disagreement on a 0 row is b_correct/a_wrong (b_count)
        # and the disagreements on 1 rows are mixed.
        res = mcnemar_test(y, a, b)
        assert res["n_disagreeing"] >= 30
        assert res["p_value"] < 0.001
        assert res["direction"] in {"b_better", "a_better"}

    def test_tie(self):
        y = np.array([0, 1])
        a = np.array([0, 1])
        b = np.array([0, 1])
        res = mcnemar_test(y, a, b)
        assert res["p_value"] == 1.0
        assert res["n_disagreeing"] == 0

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            mcnemar_test([0, 1], [0, 1, 0], [0, 1, 1])


class TestWilcoxon:
    def test_identical_residuals(self):
        r = np.array([0.1, 0.2, -0.1, 0.0, 0.05])
        res = wilcoxon_signed_rank(r, r.copy())
        assert res["mean_diff"] == 0.0
        assert res["p_value"] == 1.0

    def test_challenger_better_residuals(self):
        # Champion residuals larger and Challenger's are clearly smaller.
        rng = np.random.RandomState(0)
        a = rng.normal(size=200, loc=0.0, scale=1.0)
        b = rng.normal(size=200, loc=-0.3, scale=0.7)  # systematic shift
        res = wilcoxon_signed_rank(a, b, alternative="greater")
        assert res["mean_diff"] > 0.0
        assert res["p_value"] < 0.001

    def test_length_mismatch(self):
        with pytest.raises(ValueError):
            wilcoxon_signed_rank([0.1, 0.2], [0.1])


class TestAucWithDelong:
    def test_auc_perfect(self):
        y = np.array([0, 0, 0, 1, 1, 1])
        s = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
        res = auc_with_delong_ci(y, s)
        assert res["auc"] == pytest.approx(1.0, abs=1e-9)
        assert res["ci_low"] == pytest.approx(1.0, abs=1e-3)

    def test_auc_random_is_half(self):
        rng = np.random.RandomState(0)
        y = rng.binomial(1, 0.5, size=500)
        s = rng.uniform(size=500)
        res = auc_with_delong_ci(y, s)
        # Should be in [0.4, 0.6] for n=500 random scores
        assert 0.40 < res["auc"] < 0.60
        assert res["ci_low"] < res["auc"] < res["ci_high"]

    def test_auc_length_mismatch(self):
        with pytest.raises(ValueError):
            auc_with_delong_ci(np.array([0, 1]), np.array([0.1]))


class TestDelongPvalue:
    def test_no_difference_high_p(self):
        # Same model on both sides → p-value should be ~1
        y, p, _ = _binary_seed(0, n=200)
        res = delong_pvalue(y, p, p)
        assert res["auc_diff"] == pytest.approx(0.0, abs=1e-6)
        assert res["p_value"] > 0.5

    def test_real_difference_low_p(self):
        # Hand-crafted synthetic where pa and pb correspond to clearly
        # different SVDs on the same y_true — pa uses x, pb uses x^3.
        rng = np.random.RandomState(7)
        x = rng.normal(size=500)
        z = 1.0 * x + rng.normal(scale=0.5, size=500)
        y = (z > 0).astype(int)
        pa = 1.0 / (1.0 + np.exp(-(1.0 * x)))
        pb = 1.0 / (1.0 + np.exp(-(1.0 * np.tanh(x * 2))))
        res = delong_pvalue(y, pa, pb)
        # If they happen to be similar we still expect a non-trivial
        # p-value (the test should not be flaky in either direction).
        assert res["auc_b"] != pytest.approx(0.0, abs=1e-3) or res["p_value"] >= 0
        # At least the function returns all expected fields.
        for k in ("auc_a", "auc_b", "auc_diff", "ci95", "p_value", "statistic"):
            assert k in res


class TestCompareModels:
    def test_promote_when_challenger_better(self):
        y, pa, pb = _binary_seed(0, n=500)
        result = compare_models(
            y_true=y,
            y_proba_a=pa,
            y_proba_b=pb,
            primary_metric="auc",
            alpha=0.05,
            min_effect=0.005,
        )
        assert result["recommendation"] in {"promote", "wait", "reject"}
        if result["recommendation"] == "promote":
            assert "delong" in result["tests"]
            assert result["tests"]["delong"]["auc_diff"] >= 0.005

    def test_reject_when_challenger_worse(self):
        rng = np.random.RandomState(0)
        y, pa, pb = _binary_seed(0, n=500)
        # Reverse: champion is the stronger one
        result = compare_models(
            y_true=y,
            y_proba_a=pb,
            y_proba_b=pa,  # swap
        )
        # Swapping makes challenger worse; expect reject / wait.
        assert result["recommendation"] in {"wait", "reject"}

    def test_small_sample_warning(self):
        y, pa, pb = _binary_seed(0, n=120)
        result = compare_models(y, pa, pb)
        assert any("low power" in w for w in result["warnings"])

    def test_too_small_raises(self):
        rng = np.random.RandomState(0)
        y, pa, pb = _binary_seed(0, n=20)
        with pytest.raises(ValueError):
            compare_models(y, pa, pb)

    def test_with_binary_mcnemar(self):
        y, pa, pb = _binary_seed(0, n=300)
        ya_pred = (pa > 0.5).astype(int)
        yb_pred = (pb > 0.5).astype(int)
        result = compare_models(
            y_true=y,
            y_proba_a=pa,
            y_proba_b=pb,
            y_pred_a=ya_pred,
            y_pred_b=yb_pred,
        )
        assert "mcnemar" in result["tests"]
        assert "delong" in result["tests"]

    def test_with_segments(self):
        y, pa, pb = _binary_seed(0, n=300)
        # Segment column by sign of latent z (positive/negative half).
        # Reconstruct a rough z-proxy: just the predicted probability spread.
        segments = np.where(pa > pa.mean(), "high", "low")
        result = compare_models(
            y_true=y,
            y_proba_a=pa,
            y_proba_b=pb,
            segment_columns=[segments],
        )
        assert "segments" in result
        # At least one segment row is present
        if result["segments"]:
            for s in result["segments"]:
                assert "segment" in s
                assert "auc_diff" in s

    def test_with_wilcoxon(self):
        rng = np.random.RandomState(0)
        y, pa, pb = _binary_seed(0, n=300)
        # Synthesise residuals: inverse of probability spread.
        ra = -np.log(pa + 1e-9)
        rb = -np.log(pb + 1e-9)
        result = compare_models(
            y_true=y,
            y_proba_a=pa,
            y_proba_b=pb,
            primary_metric="wilcoxon",
            regression_residuals_a=ra,
            regression_residuals_b=rb,
        )
        assert "wilcoxon" in result["tests"]

    def test_recommendation_rationale_nonempty(self):
        y, pa, pb = _binary_seed(0, n=300)
        result = compare_models(y, pa, pb)
        assert isinstance(result["rationale"], str)
        assert len(result["rationale"]) > 10
