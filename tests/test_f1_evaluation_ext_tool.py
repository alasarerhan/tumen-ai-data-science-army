"""
Tests for ``ai_data_science_team.tools.f1_evaluation_ext`` (F1 extension tool layer).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.f1_evaluation_ext import (
    evaluate_calibration,
    evaluate_segments,
    optimize_threshold,
)


class TestEvaluateCalibration:
    def test_perfect_calibration(self):
        # Probabilities are well-calibrated bins.
        y_true = np.array([0] * 50 + [1] * 50)
        y_prob = np.zeros(100)
        # First 50 bins → predicted 0, true 0 (some slips)
        y_prob[:50] = 0.05
        y_prob[50:] = 0.95
        # first half might be 0.05 with target 0 — not perfect but let it be
        # Some noise to make a non-trivial curve.
        rng = np.random.RandomState(0)
        y_prob = np.clip(rng.normal(size=100) * 0.4 + 0.5, 0, 1)
        y_true = (y_prob + rng.normal(size=100) * 0.1 > 0.5).astype(int)
        rep = evaluate_calibration(y_true, y_prob, n_bins=5)
        assert rep.n_samples == 100
        assert rep.n_bins == 5
        # Brier score must be in [0, 1].
        assert 0 <= rep.brier_score <= 1
        # ECE non-negative.
        assert rep.ece >= 0
        # Reliability curve should have at least one entry.
        assert rep.reliability_curve

    def test_empty_input(self):
        rep = evaluate_calibration([], [])
        assert rep.n_samples == 0
        assert rep.brier_score == 0.0
        assert rep.ece == 0.0

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            evaluate_calibration([0, 1], [0.1])


class TestOptimizeThreshold:
    def test_basic_optimization(self):
        rng = np.random.RandomState(0)
        y_true = rng.binomial(1, 0.3, size=200).astype(int)
        y_prob = np.clip(rng.beta(2, 5, size=200), 0, 1)
        rep = optimize_threshold(
            y_true, y_prob, fp=1.0, fn=10.0, tn=0.0, tp=0.0, step=0.05
        )
        # Cost should be lower than baseline if FP/FN mirror class imbalance.
        assert rep.optimal_threshold is not None
        assert rep.cost_matrix == {"fp": 1.0, "fn": 10.0, "tp": 0.0, "tn": 0.0}
        assert rep.baseline_cost >= rep.expected_cost - 1e-6
        assert all(
            0 <= c["threshold"] <= 1 for c in rep.cost_curve
        )

    def test_high_fn_cost_prefers_lower_threshold(self):
        # Make positives rare; high fn_cost should pick a low threshold
        # (catch them all) compared to high fp_cost.
        y_true = np.array([0] * 80 + [1] * 20)
        y_prob = np.concatenate([np.full(80, 0.3), np.full(20, 0.6)])

        # High FN cost → threshold should be lower
        low_rep = optimize_threshold(
            y_true, y_prob, fp=1.0, fn=100.0, tn=0.0, tp=0.0, step=0.05
        )
        # High FP cost → threshold should be higher (or equal)
        high_rep = optimize_threshold(
            y_true, y_prob, fp=100.0, fn=1.0, tn=0.0, tp=0.0, step=0.05
        )
        assert low_rep.optimal_threshold <= high_rep.optimal_threshold + 1e-6

    def test_empty_input_returns_safe_defaults(self):
        rep = optimize_threshold([], [], step=0.1)
        assert rep.optimal_threshold == 0.5
        assert rep.expected_cost == 0.0


class TestEvaluateSegments:
    def test_segment_accuracy(self):
        df = pd.DataFrame(
            {
                "region": ["A"] * 4 + ["B"] * 4,
                "pred": [1, 0, 1, 1, 0, 0, 1, 0],
            }
        )
        y_true = pd.Series([1, 0, 1, 0, 0, 1, 1, 0])
        rows = evaluate_segments(
            df, y_true, df["pred"], ["region"], metric="accuracy"
        )
        assert len(rows) == 2
        for row in rows:
            assert row["metric_name"] == "accuracy"
            assert row["n"] == 4

    def test_multi_column_segment(self):
        df = pd.DataFrame(
            {
                "region": ["A", "A", "B", "B"],
                "plan": ["p1", "p2", "p1", "p2"],
                "pred": [1, 0, 1, 1],
            }
        )
        y_true = [1, 0, 1, 1]
        rows = evaluate_segments(df, y_true, df["pred"], ["region", "plan"])
        # 4 distinct combinations (region × plan).
        assert len(rows) == 4
        for row in rows:
            assert row["n"] == 1

    def test_invalid_metric_raises(self):
        df = pd.DataFrame({"a": [1, 0], "pred": [1, 0]})
        y_true = [1, 0]
        with pytest.raises(ValueError):
            evaluate_segments(df, y_true, df["pred"], ["a"], metric="xyz")

    def test_empty_segment_columns_raises(self):
        df = pd.DataFrame({"a": [1, 0]})
        y_true = [1, 0]
        with pytest.raises(ValueError):
            evaluate_segments(df, y_true, [1, 0], [])
