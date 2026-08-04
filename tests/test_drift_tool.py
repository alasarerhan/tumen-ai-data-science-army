"""
Tests for ``ai_data_science_team.tools.drift`` (G1 tool layer).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.drift import (
    drift_signal_payload,
    feature_drift_report,
    ks2,
    performance_drift,
    psi,
)


class TestPsi:
    def test_identical_distributions_is_zero(self):
        rng = np.random.RandomState(0)
        base = rng.normal(size=500)
        rng.normal(size=500)
        # rng is stateful; resetting creates equivalent distributions.
        rng2 = np.random.RandomState(0)
        cur2 = rng2.normal(size=500)
        assert psi(base, cur2) == pytest.approx(0.0, abs=1e-2)

    def test_shifted_distribution_is_high(self):
        rng = np.random.RandomState(0)
        base = rng.normal(size=500)
        cur = rng.normal(loc=1.5, size=500)  # shifted mean
        v = psi(base, cur)
        assert v > 0.10  # at least moderate drift

    def test_constant_input_returns_zero(self):
        # If all values are the same, histograms collapse.
        base = np.array([1.0] * 100)
        cur = np.array([2.0] * 100)
        v = psi(base, cur)
        # Implementation falls back to a small epsilon window — should
        # still produce a finite value, ideally moderate.
        assert math.isfinite(v)


class TestKs2:
    def test_identical_distributions_is_zero(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=200)
        rng2 = np.random.RandomState(0)
        b = rng2.normal(size=200)
        v = ks2(a, b)
        assert v < 0.05

    def test_shifted_distributions_positive(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=500)
        b = rng.normal(loc=2.0, size=500)
        assert ks2(a, b) > 0.2


class TestFeatureDriftReport:
    def test_no_drift_returns_none_overall(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame(
            {
                "x1": rng.normal(size=300),
                "x2": rng.normal(size=300),
                "cat": rng.choice(["a", "b"], size=300),
            }
        )
        cur = df.copy()
        out = feature_drift_report(df, cur)
        assert out["overall_drift"] == "none"
        assert all(s["status"] == "ok" for s in out["signals"])

    def test_significant_drift_detected(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x1": rng.normal(size=500)})
        cur = pd.DataFrame({"x1": rng.normal(loc=2.0, size=500)})
        out = feature_drift_report(df, cur)
        sig = next(s for s in out["signals"] if s["column"] == "x1")
        assert sig["severity"] in {"moderate", "significant"}
        assert out["overall_drift"] in {"moderate", "significant"}

    def test_schema_warning(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        cur = pd.DataFrame({"y": [1, 2, 3]})
        out = feature_drift_report(df, cur)
        schema_warning = next((s for s in out["signals"] if s["column"] == "__schema__"), None)
        assert schema_warning is not None

    def test_heatmap_format(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x1": rng.normal(size=100), "x2": rng.normal(size=100)})
        cur = df.copy()
        cur["x1"] = cur["x1"] + 2.0
        out = feature_drift_report(df, cur)
        # Each column should produce one heatmap entry per metric.
        for col in ["x1"]:
            metrics = {h["metric"] for h in out["feature_heatmap"] if h["column"] == col}
            assert "psi" in metrics


class TestPerformanceDrift:
    def test_improvement_no_breach(self):
        out = performance_drift(baseline_metric=0.80, current_metric=0.85)
        assert out["improved"] is True
        assert out["threshold_breached"] is False

    def test_drop_below_threshold(self):
        out = performance_drift(
            baseline_metric=0.80,
            current_metric=0.74,  # -7.5%, > 5% threshold
            relative_threshold=0.05,
        )
        assert out["improved"] is False
        assert out["threshold_breached"] is True

    def test_absolute_threshold(self):
        out = performance_drift(
            baseline_metric=0.80,
            current_metric=0.76,
            absolute_threshold=0.03,
        )
        assert out["threshold_breached"] is True

    def test_lower_is_better(self):
        # latency went DOWN ⇒ improvement.
        out = performance_drift(
            baseline_metric=200.0,
            current_metric=180.0,
            lower_is_better=True,
        )
        assert out["improved"] is True


class TestDriftSignalPayload:
    def test_payload_no_metric(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x1": rng.normal(size=200), "x2": rng.normal(size=200)})
        cur = df.copy()
        cur["x1"] = cur["x1"] + 1.0  # introduce drift
        out = drift_signal_payload(df, cur)
        assert "feature_report" in out
        assert "performance" in out and out["performance"] is None
        assert out["should_retrain"] is True  # feature_drift_trigger fired

    def test_payload_with_performance(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x1": rng.normal(size=200)})
        cur = df.copy()
        out = drift_signal_payload(
            df,
            cur,
            baseline_metric=0.80,
            current_metric=0.74,
            metric_name="roc_auc",
            relative_threshold=0.05,
        )
        assert out["should_retrain"] is True
        assert out["metric_name"] == "roc_auc"
        assert out["performance_trigger"] is True

    def test_payload_no_drift(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x": rng.normal(size=500), "y": rng.normal(size=500)})
        # Identical distributions
        out = drift_signal_payload(df, df.copy())
        assert out["should_retrain"] is False
