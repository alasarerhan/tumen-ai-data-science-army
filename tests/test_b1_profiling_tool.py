"""
Tests for ``ai_data_science_team.tools.b1_profiling`` (B1 tool layer).
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
        p = profile_column(col, name="value")
        assert p.n == 5
        assert p.n_missing == 0
        assert p.is_numeric is True
        assert p.stats["mean"] == pytest.approx(3.0)
        assert p.stats["min"] == 1.0
        assert p.stats["max"] == 5.0
        assert "histogram" in p.stats

    def test_categorical_top_values(self):
        col = pd.Series(["a", "b", "a", "c", "a"], name="letter")
        p = profile_column(col, name="letter")
        assert p.is_categorical is True
        assert p.stats["top_values"][0]["value"] == "a"
        assert p.stats["top_values"][0]["count"] == 3

    def test_missing_counted(self):
        col = pd.Series([1.0, np.nan, np.nan, 4.0])
        p = profile_column(col)
        assert p.n == 4
        assert p.n_missing == 2

    def test_pii_email_detected(self):
        col = pd.Series(["user@example.com"] * 10 + ["user2@example.com"] * 10)
        p = profile_column(col, name="email")
        assert p.pii["pii_signal"] == "high"
        assert p.pii["pii_kind"] == "email"

    def test_pii_phone_via_name_hint(self):
        col = pd.Series(["data not available"] * 5)
        # Name alone triggers "warning" + kind.
        p = profile_column(col, name="phone_number")
        assert p.pii["pii_signal"] in {"warning", "high"}
        assert p.pii["pii_kind"] == "phone"

    def test_pii_clean_numeric(self):
        col = pd.Series([1.0, 2.0, 3.0, 4.0])
        p = profile_column(col, name="value")
        assert p.pii["pii_signal"] == "low"


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
        assert prof.n_rows == 100
        assert prof.n_cols == 4
        assert len(prof.columns) == 4
        names = {c.name for c in prof.columns}
        assert names == {"user_id", "age", "email", "country"}

    def test_pii_columns_listed(self):
        df = self._toy_df()
        prof = profile_dataframe(df, include_pii_scan=True)
        assert "email" in prof.pii_columns
        # country is a benign category, age is numeric — both should be skipped.
        assert "country" not in prof.pii_columns
        assert "age" not in prof.pii_columns

    def test_pii_disabled(self):
        df = self._toy_df()
        prof = profile_dataframe(df, include_pii_scan=False)
        for c in prof.columns:
            assert c.pii["pii_signal"] == "low"
        assert prof.pii_columns == []

    def test_sampling_kicks_in(self):
        rng = np.random.RandomState(0)
        df = pd.DataFrame({"x": rng.normal(size=2000)})
        prof = profile_dataframe(df, sample_size=100)
        assert prof.n_rows == 100

    def test_schema_hash_stable(self):
        df = self._toy_df()
        h1 = profile_dataframe(df).schema_hash
        h2 = profile_dataframe(df.assign(birth_year=1990)).schema_hash
        # Same → same hash; add col → different hash.
        assert h1 == profile_dataframe(df).schema_hash
        assert h1 != h2

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        prof = profile_dataframe(df)
        assert prof.n_rows == 0
        assert prof.n_cols == 0
        assert prof.columns == []

    def test_to_dict_round_trip(self):
        df = self._toy_df()
        d = profile_dataframe(df).to_dict()
        assert "columns" in d
        assert "pii_columns" in d
        assert "schema_hash" in d
        col = next(c for c in d["columns"] if c["name"] == "email")
        assert col["pii"]["pii_kind"] == "email"
