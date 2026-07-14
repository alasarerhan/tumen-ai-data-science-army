"""Tests for J1 Autonomous Investigation tool."""
from __future__ import annotations

import pytest

import ai_data_science_team.tools.j1_investigation as j1


class TestDetectChange:
    def test_no_change(self):
        r = j1.detect_change(
            baseline_value=100.0, current_value=100.0,
        )
        assert r.detected is False
        assert r.abs_delta == 0.0

    def test_large_change_detected(self):
        r = j1.detect_change(
            baseline_value=100.0, current_value=130.0,
            historical_std=5.0, z_threshold=2.0,
        )
        assert r.detected is True
        assert r.z_score == pytest.approx(6.0, abs=1e-9)
        assert r.abs_delta == 30.0

    def test_small_change_below_relative_threshold(self):
        # 1% drop, below 5% relative threshold
        r = j1.detect_change(
            baseline_value=100.0, current_value=99.0,
            historical_std=5.0, z_threshold=2.0,
            min_relative_delta=0.05,
        )
        assert r.detected is False

    def test_zero_baseline_returns_nan_relative(self):
        r = j1.detect_change(
            baseline_value=0.0, current_value=10.0,
        )
        assert r.relative_delta != r.relative_delta  # NaN


class TestIsolateDimension:
    def test_picks_highest_delta_dimension(self):
        baseline_by_dim = {
            "country": {"TR": 100.0, "US": 80.0},
            "device": {"mobile": 90.0, "desktop": 95.0},
        }
        current_by_dim = {
            "country": {"TR": 60.0, "US": 80.0},
            "device": {"mobile": 89.0, "desktop": 94.0},
        }
        iso = j1.isolate_dimension(
            baseline_by_dim=baseline_by_dim,
            current_by_dim=current_by_dim,
        )
        assert iso.primary_dimension == "country"

    def test_no_overlap_returns_none(self):
        iso = j1.isolate_dimension(
            baseline_by_dim={"x": {"a": 1.0}},
            current_by_dim={"y": {"b": 2.0}},
        )
        assert iso.primary_dimension is None
        assert iso.dimension_scores == {}


class TestQuantifyContributors:
    def test_shares_sum_to_one(self):
        q = j1.quantify_contributors(
            baseline_total=100.0, current_total=80.0,
            contributions=[
                {"name": "A", "baseline": 50.0, "current": 30.0},
                {"name": "B", "baseline": 30.0, "current": 20.0},
                {"name": "C", "baseline": 20.0, "current": 30.0},
            ],
        )
        # total delta = -20; A=-20, B=-10, C=+10 → shares -20/-20=1.0,
        # -10/-20=0.5, 10/-20=-0.5 → ordered desc by abs
        assert q.contributors[0]["name"] == "A"
        assert q.contributors[0]["contribution_share"] == pytest.approx(1.0)

    def test_zero_total_delta_zero_shares(self):
        q = j1.quantify_contributors(
            baseline_total=100.0, current_total=100.0,
            contributions=[
                {"name": "A", "baseline": 50.0, "current": 60.0},
                {"name": "B", "baseline": 50.0, "current": 40.0},
            ],
        )
        assert all(c["contribution_share"] == 0.0 for c in q.contributors)


class TestNarrate:
    def test_narrative_shape(self):
        sig = j1.KPISignal(
            signal_id="s1", kpi_name="conversion_rate",
            baseline_value=10.0, current_value=12.0,
            timestamp=0.0,
        )
        det = j1.detect_change(baseline_value=10.0, current_value=12.0)
        iso = j1.IsolationResult(
            candidate_dimensions=["country"],
            dimension_scores={"country": 5.0},
            primary_dimension="country",
        )
        quant = j1.quantify_contributors(
            baseline_total=10.0, current_total=12.0,
            contributions=[{"name": "TR", "baseline": 5.0, "current": 7.0}],
        )
        n = j1.narrate(
            signal=sig, detection=det,
            isolation=iso, quantification=quant,
            actions=["alert team"],
        )
        assert "conversion_rate" in n.title
        assert "up" in n.title
        assert "country" in n.summary
        assert n.recommended_actions == ["alert team"]


class TestInvestigateOrchestrator:
    def test_full_pipeline(self):
        inv = j1.investigate(
            kpi_name="dau",
            baseline_value=1000.0, current_value=850.0,
            baseline_by_dim={
                "country": {"TR": 600.0, "US": 400.0},
                "device": {"mobile": 700.0, "desktop": 300.0},
            },
            current_by_dim={
                "country": {"TR": 480.0, "US": 370.0},
                "device": {"mobile": 650.0, "desktop": 200.0},
            },
            contributions=[
                {"name": "TR", "baseline": 600.0, "current": 480.0},
                {"name": "US", "baseline": 400.0, "current": 370.0},
            ],
            historical_std=30.0,
            z_threshold=2.0,
            actions=["check upstream deploy"],
        )
        assert inv.signal.kpi_name == "dau"
        assert inv.detection.abs_delta == -150.0
        assert inv.isolation.primary_dimension in ("country", "device")
        assert inv.narrative.recommended_actions == ["check upstream deploy"]

    def test_minimal_investigate(self):
        inv = j1.investigate(
            kpi_name="x", baseline_value=100.0, current_value=100.0,
        )
        assert inv.detection.detected is False


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = j1.J1_INVESTIGATION_TOOL_NAMES
        for n in ("j1_detect_change", "j1_isolate_dimension",
                  "j1_quantify_contributors", "j1_narrate",
                  "j1_investigate"):
            assert n in names
