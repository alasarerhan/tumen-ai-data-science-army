"""Tests for ``ai_data_science_team.tools.e11_time_series`` (E11 tool layer)."""

from __future__ import annotations

import pandas as pd
import pytest

import ai_data_science_team.tools.e11_time_series as e11


# ---------------------------------------------------------------------------
# Classical engines
# ---------------------------------------------------------------------------


class TestSeasonalNaive:
    def test_repeats_last_period(self):
        h = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        out = e11.seasonal_naive_forecast(h, horizon=10, period=7)
        assert out == [1, 2, 3, 4, 5, 6, 7, 1, 2, 3]

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            e11.seasonal_naive_forecast([1.0, 2.0], horizon=3, period=7)

    def test_invalid_period_raises(self):
        with pytest.raises(ValueError):
            e11.seasonal_naive_forecast([1.0] * 5, horizon=1, period=0)


class TestMovingAverage:
    def test_constant_forecast(self):
        h = [1.0, 2.0, 3.0, 4.0, 5.0]
        out = e11.moving_average_forecast(h, horizon=4, window=3)
        assert out == [4.0] * 4  # mean of last 3 is (3+4+5)/3 = 4

    def test_invalid_horizon(self):
        with pytest.raises(ValueError):
            e11.moving_average_forecast([1, 2, 3], horizon=0)


class TestMultiplicativeSeasonal:
    def test_basic(self):
        # 14 days, period 7 ⇒ 2 full periods.
        h = [10.0] * 7 + [20.0] * 7
        out = e11.multiplicative_seasonal_forecast(h, horizon=7, period=7)
        # global mean = 15, season index from last 7 = 20/15 ≈ 1.333
        # forecast = 15 * 1.333 ≈ 20 (constant per day)
        for v in out:
            assert abs(v - 20.0) < 1e-6

    def test_need_two_periods(self):
        with pytest.raises(ValueError):
            e11.multiplicative_seasonal_forecast([1, 2, 3, 4], horizon=1, period=7)


# ---------------------------------------------------------------------------
# Hierarchical reconciliation
# ---------------------------------------------------------------------------


class TestReconcileTopDown:
    def test_proportional_split(self):
        h = {"A": [10.0, 12.0], "B": [20.0, 22.0], "C": [30.0, 33.0]}
        out = e11.reconcile_top_down(100.0, h)
        # Latest values: 12, 22, 33. Total = 67. 100 * 12/67 ≈ 17.91
        s = sum(out.values())
        assert abs(s - 100.0) < 1e-9

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            e11.reconcile_top_down(100.0, {})

    def test_zero_total_falls_back_to_even(self):
        h = {"A": [0.0], "B": [0.0]}
        out = e11.reconcile_top_down(100.0, h)
        assert out == {"A": 50.0, "B": 50.0}


# ---------------------------------------------------------------------------
# Holiday calendar
# ---------------------------------------------------------------------------


class TestHolidayCalendar:
    def test_tr(self):
        out = e11.holiday_calendar("TR", [2026])
        names = [r["name"] for r in out]
        assert "Cumhuriyet Bayramı" in names
        assert "Yılbaşı" in names
        # Dates are sorted ascending.
        dates = [r["date"] for r in out]
        assert dates == sorted(dates)

    def test_us(self):
        out = e11.holiday_calendar("US", [2024, 2025])
        assert any(r["name"] == "Independence Day" for r in out)
        assert any(r["date"].startswith("2024-07-04") for r in out)
        assert any(r["date"].startswith("2025-07-04") for r in out)

    def test_invalid_country(self):
        with pytest.raises(ValueError):
            e11.holiday_calendar("FR", [2026])

    def test_int_year_argument(self):
        out = e11.holiday_calendar("TR", 2026)
        assert len(out) > 0


# ---------------------------------------------------------------------------
# Panel builder
# ---------------------------------------------------------------------------


class TestBuildPanel:
    def test_basic(self):
        df = pd.DataFrame(
            {
                "store": ["a", "a", "b", "b"],
                "ds": ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"],
                "y": [1.0, 2.0, 3.0, 4.0],
            }
        )
        out = e11.build_panel(df, group_columns=["store"], ds_column="ds", y_column="y")
        assert set(out.columns) == {"store", "ds", "y"}
        assert out["y"].sum() == 10.0

    def test_missing_columns_raise(self):
        df = pd.DataFrame({"store": ["a"], "y": [1.0]})
        with pytest.raises(ValueError):
            e11.build_panel(df, group_columns=["store"], ds_column="ds", y_column="y")

