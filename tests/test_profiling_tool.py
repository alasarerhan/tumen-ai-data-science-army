"""
Tests for ``ai_data_science_team.tools.profiling`` (B1 tool layer).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.b1_profiling import (
    profile_column,
    profile_dataframe,
)


class TestProfileColumn:
    def test_numeric_summary(self):
        col = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], name="value")
        p = profile_column(col)
        assert p["n"] == 5
        assert p["null_rate"] == 0.0
        assert p["dtype"].startswith("float")
        assert p["mean"] == pytest.approx(3.0)
        assert p["min"] == 1.0
        assert p["max"] == 5.0

    def test_categorical_top_values(self):
        col = pd.Series(["a", "b", "a", "c", "a"], name="letter")
        p = profile_column(col)
        assert p["dtype"] == "object"
        assert p["top_categories"][0][0] == "a"
        assert p["top_categories"][0][1] == 3

    def test_missing_counted(self):
        col = pd.Series([1.0, np.nan, np.nan, 4.0])
        p = profile_column(col)
        assert p["n"] == 4
        assert p["null_rate"] == pytest.approx(0.5)

    def test_pii_not_in_profile_column(self):
        # profile_column no longer performs PII detection; verify it's absent
        col = pd.Series(["user@example.com"] * 10, name="email")
        p = profile_column(col)
        assert "pii" not in p

    def test_phone_column_name_hint(self):
        # profile_column no longer performs PII detection; just verify dict shape
        col = pd.Series(["data not available"] * 5, name="phone_number")
        p = profile_column(col)
        assert p["n"] == 5
        assert "name" not in p or p.get("name") == "phone_number"

    def test_clean_numeric_column(self):
        col = pd.Series([1.0, 2.0, 3.0, 4.0], name="value")
        p = profile_column(col)
        assert p["n"] == 4
        assert p["null_rate"] == 0.0


class TestProfileDataframe:
    def _toy_df(self) -> pd.DataFrame:
        rng = np.random.RandomState(0)
        return pd.DataFrame(
            {
                "user_id": np.arange(100),
                "age": rng.randint(20, 60, size=100).astype(float),
                "email": ["user@example.com"] * 100,
                "country": rng.choice(["TR", "US", "DE"], size=100),
            }
        )

    def test_basic_profile_shape(self):
        df = self._toy_df()
        prof = profile_dataframe(df)
        assert prof["n_rows"] == 100
        assert len(prof["columns"]) == 4
        assert set(prof["columns"]) == {"user_id", "age", "email", "country"}
        assert "age" in prof["numeric_cols"]

    def test_column_types_identified(self):
        df = self._toy_df()
        prof = profile_dataframe(df)
        assert "age" in prof["numeric_cols"]
        assert "email" in prof["categorical_cols"]
        assert "country" in prof["categorical_cols"]

    def test_low_cardinality_numeric_detected(self):
        rng = np.random.RandomState(42)
        df = pd.DataFrame(
            {"flag": rng.randint(0, 3, size=100).astype(float), "value": rng.normal(size=100)}
        )
        prof = profile_dataframe(df)
        assert "flag" in prof["low_cardinality_numeric"]
        assert "value" not in prof["low_cardinality_numeric"]

    def test_profile_is_dict(self):
        df = self._toy_df()
        prof = profile_dataframe(df)
        assert isinstance(prof, dict)
        assert "n_rows" in prof
        assert "columns" in prof

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        prof = profile_dataframe(df)
        assert prof["n_rows"] == 0
        assert prof["columns"] == []

    def test_dataframe_from_dict(self):
        data = {"x": [1, 2, 3], "y": ["a", "b", "c"]}
        prof = profile_dataframe(data)
        assert prof["n_rows"] == 3
        assert set(prof["columns"]) == {"x", "y"}
