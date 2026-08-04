"""Tests for ``ai_data_science_team.tools.kpi`` (C3 tool layer)."""

from __future__ import annotations

import pandas as pd
import pytest

from ai_data_science_team.tools.kpi import (
    build_alarm,
    check_alarm,
    compute_schedule,
    define_kpi,
    evaluate_and_record,
    evaluate_python_code,
    make_history,
    sparkline_points,
)

# ---------------------------------------------------------------------------
# define_kpi / evaluate_python_code
# ---------------------------------------------------------------------------


class TestDefineKPI:
    def test_basic_python_kpi(self):
        k = define_kpi(
            name="Daily Active",
            code="len(df)",
            period="daily",
            target=1000,
            unit="users",
        )
        assert k["name"] == "Daily Active"
        assert k["code"] == "len(df)"
        assert k["kind"] == "python"
        assert k["period"] == "daily"
        assert k["target"] == 1000.0
        assert k["unit"] == "users"
        assert len(k["kpi_id"]) > 5

    def test_invalid_period(self):
        with pytest.raises(ValueError):
            define_kpi(name="x", code="len(df)", period="hour_ish")

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            define_kpi(name="x", code="len(df)", kind="fortran")


class TestEvaluatePython:
    def test_simple_len(self):
        df = pd.DataFrame({"x": [1, 2, 3, 4]})
        k = define_kpi(name="count", code="len(df)")
        out = evaluate_python_code(k, df)
        assert out["value"] == 4
        assert out["error"] is None

    def test_mean_with_safe_global(self):
        df = pd.DataFrame({"x": [10, 20, 30]})
        k = define_kpi(name="avg", code="mean(df['x'].tolist())")
        out = evaluate_python_code(k, df)
        assert out["value"] == 20.0

    def test_syntax_error_reported(self):
        df = pd.DataFrame({"x": [1]})
        k = define_kpi(name="x", code="def broken;")
        out = evaluate_python_code(k, df)
        assert out["value"] is None
        assert out["error"] is not None

    def test_non_numeric_return_value(self):
        df = pd.DataFrame({"x": [1]})
        k = define_kpi(name="x", code="'hello'")
        out = evaluate_python_code(k, df)
        assert out["error"] is not None

    def test_sql_kind_returns_error(self):
        df = pd.DataFrame({"x": [1]})
        k = define_kpi(name="x", code="SELECT 1", kind="sql")
        out = evaluate_python_code(k, df)
        assert out["value"] is None
        assert "sql" in out["error"].lower() or "engine" in out["error"].lower()

    def test_empty_code(self):
        df = pd.DataFrame({"x": [1]})
        k = define_kpi(name="x", code="  ")
        out = evaluate_python_code(k, df)
        assert out["error"] == "empty code"

    def test_built_ins_disabled(self):
        df = pd.DataFrame({"x": [1]})
        k = define_kpi(name="x", code="__import__('os').system('rm -rf /')")
        out = evaluate_python_code(k, df)
        assert out["value"] is None


class TestComputeSchedule:
    def test_returns_n_steps_backwards(self):
        s = compute_schedule(period="daily", starting_at_ts=10_000_000, lookback_steps=5)
        assert [step["ts"] for step in s] == [10_000_000 - i * 86_400 for i in range(5)]


# ---------------------------------------------------------------------------
# KPIHistory + evaluate_and_record
# ---------------------------------------------------------------------------


class TestHistory:
    def test_append_and_record(self):
        k = define_kpi(name="count", code="len(df)")
        hist = make_history(k["kpi_id"])
        df = pd.DataFrame({"x": [1, 2, 3]})
        evaluate_and_record(k, df, hist, timestamp=100)
        out = evaluate_and_record(k, df, hist, timestamp=200)
        assert "values" in out
        assert hist.values == [3.0, 3.0]
        assert hist.timestamps == [100, 200]

    def test_sql_kpi_returns_deferred(self):
        k = define_kpi(name="x", code="SELECT 1", kind="sql")
        hist = make_history(k["kpi_id"])
        out = evaluate_and_record(k, pd.DataFrame({"a": [1]}), hist)
        assert out.get("deferred") is True


# ---------------------------------------------------------------------------
# Alarms
# ---------------------------------------------------------------------------


class TestAlarm:
    def test_absolute_fires(self):
        rule = build_alarm("k", kind="absolute", threshold=10.0)
        assert check_alarm(rule, history=[5.0, 8.0, 4.0])["fired"] is True
        assert check_alarm(rule, history=[12.0, 15.0])["fired"] is False

    def test_relative_fires_on_drop(self):
        rule = build_alarm("k", kind="relative", relative_threshold=-0.10)
        # Baseline 100, dropped to 85: -0.15 → fires.
        assert check_alarm(rule, history=[100, 100, 85])["fired"] is True
        # Drop to 95: -0.05 → does not fire.
        assert check_alarm(rule, history=[100, 100, 95])["fired"] is False

    def test_anomaly_fires_on_outlier(self):
        rule = build_alarm("k", kind="anomaly", window=5, sensitivity=2.0)
        # Mostly 10 ± 0.5; outlier is 25.
        hist = [10.0, 10.1, 9.9, 10.0, 10.1, 9.9, 10.0, 10.1, 9.9, 10.0, 25.0]
        out = check_alarm(rule, history=hist)
        assert out["fired"] is True

    def test_anomaly_too_short_history(self):
        rule = build_alarm("k", kind="anomaly", window=5)
        # Two points: not enough to evaluate anomaly → fired=False.
        out = check_alarm(rule, history=[1.0, 2.0])
        assert out["fired"] is False

    def test_relative_zero_baseline(self):
        rule = build_alarm("k", kind="relative", relative_threshold=-0.50)
        out = check_alarm(rule, history=[0.0, 0.0, 0.0])
        # Baseline was 0; relative cannot be computed → not fired.
        assert out["fired"] is False

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            build_alarm("k", kind="nonsense")

    def test_window_too_small_for_anomaly(self):
        with pytest.raises(ValueError):
            build_alarm("k", kind="anomaly", window=1)

    def test_alarm_serialise_roundtrip(self):
        rule = build_alarm("k", kind="relative", relative_threshold=-0.05)
        d = rule.to_dict()
        assert d["kind"] == "relative"
        assert d["relative_threshold"] == -0.05


# ---------------------------------------------------------------------------
# Sparkline
# ---------------------------------------------------------------------------


class TestSparkline:
    def test_shorter_input_pads_with_first(self):
        out = sparkline_points([1.0, 2.0], n=5)
        assert len(out) == 5
        assert out[-1] == 2.0
        assert out[0] == 1.0

    def test_single_value(self):
        out = sparkline_points([42.0], n=4)
        assert out == [42.0, 42.0, 42.0, 42.0]

    def test_empty_pads_with_none(self):
        out = sparkline_points([], n=3)
        assert out == [None, None, None]

    def test_longer_input_downsamples(self):
        seq = [float(i) for i in range(100)]
        out = sparkline_points(seq, n=10)
        assert len(out) == 10
        # 100 / 10 = 10 elements per bin → bin 0 has [0..9], mean ≈ 4.5
        assert 4.0 <= out[0] <= 5.0
        # Last bin has [90..99] → mean ≈ 94.5
        assert 94.0 <= out[-1] <= 95.0
