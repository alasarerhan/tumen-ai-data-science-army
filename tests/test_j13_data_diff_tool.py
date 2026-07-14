"""Tests for J13 Data Diff tool."""
from __future__ import annotations

import math

import pandas as pd
import pytest

import ai_data_science_team.tools.j13_data_diff as j13


@pytest.fixture
def left_df():
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "feature_a": [0.1, 0.2, 0.3, 0.4, 0.5],
        "feature_b": [10.0, 20.0, 30.0, 40.0, 50.0],
        "country": ["TR", "US", "DE", "TR", "FR"],
    })


@pytest.fixture
def right_df():
    """Schema drift: feature_a kept, feature_b removed, country kept,
    region added. Numeric drift on feature_a (mean 0.3 -> 0.6).
    id 5 removed, 6 added."""
    return pd.DataFrame({
        "id": [1, 2, 3, 4, 6],
        "feature_a": [0.2, 0.4, 0.6, 0.8, 1.0],
        "country": ["TR", "US", "DE", "TR", "FR"],
        "region": ["EU", "NA", "EU", "EU", "NA"],
    })


class TestProfileColumns:
    def test_basic_profile(self, left_df):
        stats = j13.profile_columns(left_df)
        assert set(stats.keys()) == set(left_df.columns)
        assert stats["id"].n_unique == 5
        assert stats["feature_a"].dtype.startswith("float")

    def test_null_rate(self):
        df = pd.DataFrame({"x": [1.0, None, 3.0, None]})
        stats = j13.profile_columns(df)
        assert pytest.approx(stats["x"].null_rate, abs=1e-9) == 0.5


class TestSchemaDelta:
    def test_basic(self, left_df, right_df):
        added, removed, common = j13.schema_delta(left_df, right_df)
        assert added == ["region"]
        assert removed == ["feature_b"]
        assert "feature_a" in common and "country" in common and "id" in common


class TestKeySetDiff:
    def test_basic(self, left_df, right_df):
        only_l, only_r = j13.key_set_diff(left_df, right_df, "id")
        assert only_l == {5}
        assert only_r == {6}

    def test_unknown_key(self, left_df, right_df):
        with pytest.raises(KeyError):
            j13.key_set_diff(left_df, right_df, "missing")


class TestNumericShift:
    def test_basic(self):
        s1 = pd.Series([1.0, 2.0, 3.0])
        s2 = pd.Series([2.0, 3.0, 4.0])
        shift = j13.numeric_shift(s1, s2)
        assert pytest.approx(shift["mean_shift"], abs=1e-9) == 1.0
        assert shift["cardinality_left"] == 3

    def test_with_nulls(self):
        s1 = pd.Series([1.0, None, 3.0, None])
        s2 = pd.Series([1.0, 2.0, 3.0, None])
        shift = j13.numeric_shift(s1, s2)
        assert pytest.approx(shift["null_rate_left"], abs=1e-9) == 0.5
        assert pytest.approx(shift["null_rate_right"], abs=1e-9) == 0.25


class TestDiffSummary:
    def test_no_key_row_counts(self, left_df, right_df):
        s = j13.diff_summary(left_df, right_df)
        # left=5, right=5; same count → no added/removed row attribution
        assert s.rows_left == 5
        assert s.rows_right == 5
        assert s.rows_added == 0
        assert s.rows_removed == 0

    def test_with_key(self, left_df, right_df):
        s = j13.diff_summary(left_df, right_df, key="id")
        assert s.rows_added == 1  # id=6
        assert s.rows_removed == 1  # id=5

    def test_drift_detection(self, left_df, right_df):
        s = j13.diff_summary(left_df, right_df, key="id",
                             drift_threshold=0.10)
        # feature_a mean shift = 0.3 (left mean=0.3, right mean=0.6)
        assert "feature_a" in s.drift_columns

    def test_no_drift_when_similar(self, left_df):
        right = left_df.copy()
        right["feature_a"] = left_df["feature_a"] + 0.001
        s = j13.diff_summary(left_df, right, drift_threshold=0.10)
        assert s.drift_columns == []

    def test_column_added_removed(self, left_df, right_df):
        s = j13.diff_summary(left_df, right_df)
        assert s.columns_added == ["region"]
        assert s.columns_removed == ["feature_b"]

    def test_non_numeric_column_no_crash(self, left_df, right_df):
        s = j13.diff_summary(left_df, right_df, key="id")
        assert "country" in s.column_stats
        # non-numeric: all mean fields NaN
        assert math.isnan(s.column_stats["country"]["left_mean"])


class TestDiffPayload:
    def test_payload_structure(self, left_df, right_df):
        p = j13.diff_payload(left_df, right_df, key="id")
        assert "rows_left" in p
        assert "drift_columns" in p
        assert "column_stats" in p
        assert p["rows_added"] == 1
        assert p["rows_removed"] == 1

    def test_payload_serializable(self, left_df, right_df):
        import json
        p = j13.diff_payload(left_df, right_df, key="id")
        json.dumps(p)  # should not raise


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = j13.J13_DATA_DIFF_TOOL_NAMES
        for n in ("j13_profile_columns", "j13_schema_delta",
                  "j13_key_set_diff", "j13_diff_summary",
                  "j13_diff_payload"):
            assert n in names
