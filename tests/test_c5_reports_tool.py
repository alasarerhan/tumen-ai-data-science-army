"""Tests for ``ai_data_science_team.tools.c5_reports`` (C5 tool layer)."""

from __future__ import annotations

import time

import pytest

from ai_data_science_team.tools.c5_reports import (
    TEMPLATES,
    build_report,
    compute_schedule,
    get_template,
    render_markdown,
)


class TestGetTemplate:
    def test_known(self):
        tpl = get_template("weekly_kpi_summary")
        assert tpl["title"] == "Weekly KPI Summary"

    def test_unknown(self):
        with pytest.raises(KeyError):
            get_template("not_a_template")


class TestBuildReport:
    def test_weekly_kpi_summary(self):
        report = build_report(
            "weekly_kpi_summary",
            period_start="2026-07-01",
            period_end="2026-07-07",
            kpis=[
                {"name": "DAU", "value": 1234, "delta": 50},
                {"name": "Conv", "value": 0.05, "delta": -0.001},
            ],
            anomalies=["Spike 14:00 Tue"],
        )
        assert report["template_id"] == "weekly_kpi_summary"
        assert "header" in report
        assert "kpis" in report
        assert "anomalies" in report
        # Trends derived from kpi delta sign.
        assert report["trends"][0]["direction"] == "up"
        assert report["trends"][1]["direction"] == "down"

    def test_experiment_results(self):
        report = build_report(
            "experiment_results",
            design_summary="XGB vs baseline",
            metrics=[{"name": "AUC", "value": 0.91, "p_value": 0.012}],
            decision="promote_b",
            next_steps=["Deploy to 50%", "Monitor drift"],
        )
        assert "metrics" in report
        assert report["decision"] == "promote_b"

    def test_drift_alert(self):
        report = build_report(
            "model_drift_alert",
            drift_signals=[
                {"column": "x1", "psi": 0.31, "severity": "moderate"},
            ],
            retrain_recommendation="Trigger F2 auto-retrain",
        )
        assert "drift_signals" in report
        assert "retrain_recommendation" in report

    def test_fairness_audit(self):
        report = build_report(
            "fairness_audit_summary",
            protected_attribute_metrics=[
                {"attribute": "gender", "group": "F", "metric": "selection_rate", "value": 0.08},
            ],
            recommendations=["Re-balance training set"],
        )
        assert "protected_attribute_metrics" in report
        assert "recommendations" in report

    def test_unknown_template_raises(self):
        with pytest.raises(KeyError):
            build_report("not_a_template")

    def test_auto_id(self):
        r = build_report("weekly_kpi_summary")
        assert r["report_id"].startswith("rpt_")


class TestComputeSchedule:
    def test_daily(self):
        s = compute_schedule("daily", starting_at_epoch=0.0, n_runs=3)
        assert s == [0.0, 86_400.0, 172_800.0]

    def test_weekly(self):
        s = compute_schedule("weekly", starting_at_epoch=0.0, n_runs=2)
        assert s == [0.0, 86_400.0 * 7]

    def test_oneoff(self):
        s = compute_schedule("oneoff", starting_at_epoch=123.0, n_runs=3)
        assert s == [123.0, 123.0, 123.0]

    def test_event(self):
        s = compute_schedule("event", starting_at_epoch=42.0, n_runs=2)
        assert s == [42.0, 42.0]

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError):
            compute_schedule("biyearly", starting_at_epoch=0.0)


class TestRenderMarkdown:
    def test_renders_kpis(self):
        report = build_report(
            "weekly_kpi_summary",
            kpis=[{"name": "DAU", "value": 100, "delta": 1}],
        )
        md = render_markdown(report)
        assert "# Weekly KPI Summary" in md
        assert "DAU" in md
        assert "100" in md

    def test_renders_metrics_with_p_value(self):
        report = build_report(
            "experiment_results",
            metrics=[{"name": "AUC", "value": 0.92, "p_value": 0.003}],
            decision="promote_b",
        )
        md = render_markdown(report)
        assert "## Metrics" in md
        assert "AUC" in md
        assert "p=0.003" in md
        assert "promote_b" in md

    def test_renders_drift_signals(self):
        report = build_report(
            "model_drift_alert",
            drift_signals=[{"column": "x1", "psi": 0.31, "severity": "moderate"}],
            retrain_recommendation="trigger",
        )
        md = render_markdown(report)
        assert "## Drift Signals" in md
        assert "x1" in md
        assert "psi=0.31" in md

    def test_renders_fairness_table(self):
        report = build_report(
            "fairness_audit_summary",
            protected_attribute_metrics=[
                {"attribute": "gender", "group": "F", "metric": "rate", "value": 0.08},
            ],
            recommendations=["A"],
        )
        md = render_markdown(report)
        assert "## Protected-attribute Metrics" in md
        assert "gender" in md

    def test_empty_report_does_not_crash(self):
        md = render_markdown({})
        assert "# Report" in md
