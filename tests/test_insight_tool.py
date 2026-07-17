"""Tests for ``ai_data_science_team.tools.insight`` (C1 tool layer)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.insight import (
    ALL_KINDS,
    KIND_ANOMALY,
    KIND_CORRELATION,
    KIND_CONSTANT,
    KIND_IMBALANCE,
    KIND_MISSING,
    KIND_SKEW,
    find_anomalies,
    find_class_imbalance,
    find_constants_and_outliers,
    find_missing_patterns,
    find_skewness,
    find_strong_correlations,
    mine_insights,
)


def _toy():
    rng = np.random.RandomState(0)
    n = 200
    return pd.DataFrame(
        {
            "x1": rng.normal(size=n),  # normal
            "x2": np.exp(rng.normal(size=n)),  # right-skewed
            "x3": rng.choice(["a", "b"], size=n, p=[0.95, 0.05]),  # imbalance
            "constant": ["x"] * n,
        }
    )


class TestFindAnomalies:
    def test_no_anomaly_on_clean_data(self):
        df = pd.DataFrame({"x": np.random.RandomState(0).normal(size=500)})
        assert find_anomalies(df) == []

    def test_extreme_value_picked_up(self):
        df = pd.DataFrame({"x": np.array([0.0] * 99 + [50.0])})
        ins = find_anomalies(df)
        assert any(i.kind == KIND_ANOMALY for i in ins)
        assert any("Anomalous" in i.title for i in ins)


class TestFindStrongCorrelations:
    def test_no_correlation(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"a": rng.normal(size=200), "b": rng.normal(size=200)})
        assert find_strong_correlations(df, threshold=0.7) == []

    def test_perfect_corr(self):
        x = np.arange(100, dtype=float)
        df = pd.DataFrame({"a": x, "b": x * 2 + 1})
        ins = find_strong_correlations(df, threshold=0.7)
        assert len(ins) >= 1
        assert ins[0].kind == KIND_CORRELATION
        assert ins[0].evidence["abs_corr"] == pytest.approx(1.0)


class TestFindSkewness:
    def test_normal_distribution_low(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x": rng.normal(size=1000)})
        assert find_skewness(df) == []

    def test_exp_is_skewed(self):
        df = pd.DataFrame({"x": np.exp(np.random.RandomState(0).normal(size=200))})
        ins = find_skewness(df)
        assert any(i.kind == KIND_SKEW for i in ins)


class TestFindMissingPatterns:
    def test_no_missing(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        assert find_missing_patterns(df) == []

    def test_high_null_rate_caught(self):
        df = pd.DataFrame({"a": [1.0, 2.0, None, None, None, None]})
        ins = find_missing_patterns(df, rate_threshold=0.1)
        assert any(i.kind == KIND_MISSING for i in ins)
        assert any("`a`" in i.title for i in ins)

    def test_co_missing_pair_caught(self):
        df = pd.DataFrame(
            {
                "a": [1.0, None, None, None, None, None, None, None, None, None, 2.0],
                "b": [10.0, None, None, None, None, None, None, None, None, None, 20.0],
            }
        )
        ins = find_missing_patterns(df, rate_threshold=0.1)
        co = [i for i in ins if "Co-missing" in i.title]
        assert co, [i.title for i in ins]


class TestFindClassImbalance:
    def test_balanced_no_insight(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"y": rng.choice(["a", "b", "c"], size=300)})
        assert find_class_imbalance(df) == []

    def test_imbalance_caught(self):
        df = pd.DataFrame({"y": ["a"] * 95 + ["b"] * 5})
        ins = find_class_imbalance(df)
        assert any(i.kind == KIND_IMBALANCE for i in ins)


class TestFindConstants:
    def test_constant_caught(self):
        df = pd.DataFrame({"a": [1] * 50})
        ins = find_constants_and_outliers(df)
        assert any(i.kind == KIND_CONSTANT for i in ins)


class TestMineInsights:
    def test_orchestrator(self):
        df = _toy()
        out = mine_insights(df, top_k=10)
        # At least one of each kind should surface in the toy data.
        kinds = {i["kind"] for i in out}
        assert KIND_CONSTANT in kinds
        assert KIND_IMBALANCE in kinds or KIND_SKEW in kinds

    def test_empty_dataframe(self):
        assert mine_insights(pd.DataFrame()) == []

    def test_include_exclude(self):
        df = _toy()
        out = mine_insights(df, include=["x1"], top_k=10)
        # No insight should mention x2 or x3 or constant.
        for i in out:
            for col in i["columns"]:
                assert col in {"x1"}

    def test_sorting_by_score(self):
        df = _toy()
        out = mine_insights(df, top_k=20)
        scores = [i["score"] for i in out]
        assert scores == sorted(scores, reverse=True)

    def test_all_kinds_constant(self):
        assert isinstance(ALL_KINDS, list)
        assert "anomaly" in ALL_KINDS
        assert "correlation" in ALL_KINDS
