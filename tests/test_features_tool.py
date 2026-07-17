"""Tests for ``ai_data_science_team.tools.features`` (D2 tool layer)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.features import (
    detect_leakage,
    filter_scores,
    multicollinearity_report,
    select_embedded,
    select_feature,
    select_filter,
    select_wrapper,
)


def _synthetic(n=400, seed=0):
    rng = np.random.RandomState(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    noise = rng.normal(scale=0.5, size=n)
    z = 1.5 * x1 + 0.5 * x2 + noise
    y = (z > 0).astype(int)
    return pd.DataFrame({"x1": x1, "x2": x2, "x3": x3}), pd.Series(y)


# ---------------------------------------------------------------------------
# filter_scores
# ---------------------------------------------------------------------------


class TestFilterScores:
    def test_correlation_picks_strongest(self):
        df, y = _synthetic()
        scored = filter_scores(df, y, method="correlation")
        names = [s["feature"] for s in scored]
        assert names[0] == "x1"
        assert scored[0]["score"] > scored[-1]["score"]

    def test_scores_sorted_descending(self):
        df, y = _synthetic()
        scored = filter_scores(df, y, method="correlation")
        for a, b in zip(scored, scored[1:]):
            assert a["score"] >= b["score"]

    def test_mutual_info_returns_non_negative(self):
        df, y = _synthetic()
        scored = filter_scores(df, y, method="mutual_info")
        assert all(s["score"] >= 0 for s in scored)

    def test_invalid_method_raises(self):
        df, y = _synthetic()
        with pytest.raises(ValueError):
            filter_scores(df, y, method="mystery")


# ---------------------------------------------------------------------------
# select_filter / wrapper / embedded
# ---------------------------------------------------------------------------


class TestSelectFilter:
    def test_top_k_returns_sorted(self):
        df, y = _synthetic()
        chosen = select_filter(df, y, top_k=2)
        assert len(chosen) == 2
        assert "x1" in chosen

    def test_zero_k_raises(self):
        df, y = _synthetic()
        with pytest.raises(ValueError):
            select_filter(df, y, top_k=0)


class TestSelectWrapper:
    def test_returns_up_to_max_features(self):
        df, y = _synthetic()
        chosen = select_wrapper(df, y, max_features=2)
        assert len(chosen) <= 2

    def test_picks_distinct(self):
        df, y = _synthetic()
        chosen = select_wrapper(df, y, max_features=3)
        assert len(set(chosen)) == len(chosen)

    def test_zero_max_features_raises(self):
        df, y = _synthetic()
        with pytest.raises(ValueError):
            select_wrapper(df, y, max_features=0)


class TestSelectEmbedded:
    def test_binary_l1_picks_some(self):
        df, y = _synthetic()
        rows = select_embedded(df, y)
        assert isinstance(rows, list)
        # x1 must survive; x3 might be dropped (zero coefficient).
        selected = [r["feature"] for r in rows if r["selected"]]
        assert "x1" in selected

    def test_alpha_override(self):
        df, y = _synthetic()
        rows = select_embedded(df, y, alpha=0.01)
        selected = [r["feature"] for r in rows if r["selected"]]
        # low alpha → at least one feature should survive.
        assert len(selected) >= 1


class TestSelectFeatureDispatch:
    def test_filter(self):
        df, y = _synthetic()
        out = select_feature(df, y, method="filter", top_k=2)
        assert out["method"] == "filter"

    def test_wrapper(self):
        df, y = _synthetic()
        out = select_feature(df, y, method="wrapper", max_features=2)
        assert out["method"] == "wrapper"

    def test_embedded(self):
        df, y = _synthetic()
        out = select_feature(df, y, method="embedded")
        assert out["method"] == "embedded"
        assert "selected" in out

    def test_unknown_raises(self):
        df, y = _synthetic()
        with pytest.raises(ValueError):
            select_feature(df, y, method="mystery")


# ---------------------------------------------------------------------------
# detect_leakage
# ---------------------------------------------------------------------------


class TestDetectLeakage:
    def test_perfect_correlation_caught(self):
        rng = np.random.RandomState(0)
        x = rng.normal(size=300)
        df = pd.DataFrame({"leakage_col": x, "x1": rng.normal(size=300)})
        # Continuous target that's essentially a function of x.
        y = pd.Series(x + rng.normal(size=300, scale=0.001))
        report = detect_leakage(df, y, threshold=0.7)
        assert "leakage_col" in report.suspect_columns

    def test_suffix_match_caught(self):
        rng = np.random.RandomState(0)
        # Spec's suffix list uses ``_after_`` (with trailing underscore)
        # so we use a column name that ends with that exact suffix.
        df = pd.DataFrame(
            {
                "metric_after_": rng.normal(size=50),
                "x": rng.normal(size=50),
            }
        )
        y = rng.normal(size=50)
        report = detect_leakage(df, pd.Series(y), threshold=0.99)
        assert "metric_after_" in report.suspect_columns
        f = next(
            r for r in report.findings if r.column == "metric_after_"
        )
        assert "suffix" in f.reason

    def test_clean_features_no_suspects(self):
        df, y = _synthetic()
        report = detect_leakage(df, y, threshold=0.99)
        assert report.suspect_columns == []

    def test_target_skipped(self):
        df = pd.DataFrame({"x": np.random.RandomState(0).normal(size=50)})
        y = pd.Series([0, 1] * 25)
        report = detect_leakage(df, y, target_name="x")
        # target column not flagged as leakage against itself.
        assert "x" not in report.suspect_columns

    def test_to_dict_shape(self):
        df, y = _synthetic()
        d = detect_leakage(df, y).to_dict()
        assert "suspect_columns" in d
        assert "findings" in d


# ---------------------------------------------------------------------------
# multicollinearity_report
# ---------------------------------------------------------------------------


class TestMulticollinearityReport:
    def test_perfect_corr_pair_marked_high(self):
        df = pd.DataFrame(
            {
                "x1": np.random.RandomState(0).normal(size=100),
                "x2": np.random.RandomState(0).normal(size=100),
                "y": np.random.RandomState(0).normal(size=100),
            }
        )
        df["x2"] = df["x1"] + np.random.RandomState(1).normal(size=100, scale=0.01)
        df = df.drop(columns=["y"])
        report = multicollinearity_report(df)
        pairs = report["high_correlation_pairs"]
        labels = [p["label"] for p in pairs]
        assert "high" in labels

    def test_high_vif_columns_listed(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame(
            {
                "x1": rng.normal(size=100),
                "x2": rng.normal(size=100),
                "x3": rng.normal(size=100),
            }
        )
        df["x4"] = 2 * df["x1"] + rng.normal(size=100, scale=0.001)
        report = multicollinearity_report(df, threshold=2.0)
        assert "x4" in report["high_vif"]

    def test_empty_numeric_returns_zero_shapes(self):
        df = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
        report = multicollinearity_report(df)
        assert report["vif"] == {}
        assert report["correlation_matrix"]["columns"] == []
        assert report["high_vif"] == []

    def test_vif_values_positive(self):
        df, _ = _synthetic()
        report = multicollinearity_report(df)
        for v in report["vif"].values():
            assert v is None or v > 0
