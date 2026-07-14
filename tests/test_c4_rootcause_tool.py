"""Tests for ``ai_data_science_team.tools.c4_rootcause`` (C4 tool layer)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.tools.c4_rootcause import (
    drill_down,
    render_narrative,
    waterfall,
)


def _toy_df(n=200, seed=0):
    rng = np.random.RandomState(seed)
    region = rng.choice(["EU", "US", "APAC"], size=n)
    device = rng.choice(["ios", "android", "web"], size=n)
    base = rng.normal(size=n, loc=10)
    uplift = np.where(
        region == "EU",
        rng.normal(size=n, loc=2.0),
        np.where(region == "US", rng.normal(size=n, loc=0.5), rng.normal(size=n, loc=0.0)),
    )
    metric = base + uplift
    return pd.DataFrame(
        {
            "month": ["A"] * (n // 2) + ["B"] * (n - n // 2),
            "region": region,
            "device": device,
            "metric": metric,
        }
    )


# ---------------------------------------------------------------------------
# Waterfall
# ---------------------------------------------------------------------------


class TestWaterfall:
    def test_basic_decomposition(self):
        df = _toy_df()
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        # Two totals should differ because EU uplift differs.
        assert res.baseline_total != res.current_total
        # Three regions.
        assert len(res.segments) == 3
        # All three regions have a sample > 0.
        assert all(s.sample_size > 0 for s in res.segments)

    def test_top_drivers_and_drains(self):
        # Use a clean deterministic fixture: in month A all regions
        # have metric=10, in month B the regional deltas are:
        #   EU: +5, US: -3, APAC: 0  → EU is the top driver, US the top drain.
        df = pd.DataFrame(
            {
                "month": ["A"] * 30 + ["B"] * 30,
                "region": (["EU"] * 10 + ["US"] * 10 + ["APAC"] * 10) * 2,
                "metric": (
                    [10.0] * 30
                    + [15.0] * 10 + [7.0] * 10 + [10.0] * 10
                ),
            }
        )
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        assert res.top_drivers
        top_seg = res.top_drivers[0]["segment"]
        assert top_seg == "EU"
        assert res.top_drains
        assert res.top_drains[0]["segment"] == "US"

    def test_contribution_shares_sum_to_one(self):
        # Use the deterministic fixture so the totals add up cleanly.
        df = pd.DataFrame(
            {
                "month": ["A"] * 30 + ["B"] * 30,
                "region": (["EU"] * 10 + ["US"] * 10 + ["APAC"] * 10) * 2,
                "metric": (
                    [10.0] * 30
                    + [15.0] * 10 + [7.0] * 10 + [10.0] * 10
                ),
            }
        )
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        if res.total_delta != 0:
            total_share = sum(s.contribution_share for s in res.segments)
            assert total_share == pytest.approx(1.0, abs=1e-9)

    def test_top_n_caps(self):
        df = _toy_df()
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
            top_n=1,
        )
        assert len(res.top_drivers) <= 1
        assert len(res.top_drains) <= 1

    def test_invalid_window_query_raises(self):
        df = _toy_df()
        with pytest.raises(Exception):  # noqa: BLE001 — pandas raises
            waterfall(
                df,
                metric_col="metric",
                dimension="region",
                baseline_window={"query": "this is not valid python >>>"},
                current_window={"query": "month == 'B'"},
            )

    def test_invalid_metric_column_raises(self):
        df = _toy_df()
        with pytest.raises(ValueError):
            waterfall(
                df,
                metric_col="missing",
                dimension="region",
                baseline_window={"query": "month == 'A'"},
                current_window={"query": "month == 'B'"},
            )

    def test_aggregate_sum(self):
        df = _toy_df()
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
            agg="sum",
        )
        # Sum should be larger than mean.
        assert res.baseline_total > 0

    def test_to_dict_shape(self):
        df = _toy_df()
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        d = res.to_dict()
        for k in ("metric", "dimension", "aggregation", "segments", "top_drivers"):
            assert k in d


# ---------------------------------------------------------------------------
# Drill-down
# ---------------------------------------------------------------------------


class TestDrillDown:
    def test_drill_returns_child_slices(self):
        df = _toy_df()
        out = drill_down(
            df,
            metric_col="metric",
            dimension="region",
            parent_value="EU",
            child_dimension="device",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        assert out.parent_value == "EU"
        assert out.parent_dimension == "region"
        assert out.child_dimension == "device"
        # Three device types.
        assert {s.child for s in out.slices} == {"ios", "android", "web"}

    def test_top_drivers_ranked(self):
        df = _toy_df()
        out = drill_down(
            df,
            metric_col="metric",
            dimension="region",
            parent_value="EU",
            child_dimension="device",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        deltas = [abs(s["delta"]) for s in out.top_drivers]
        assert deltas == sorted(deltas, reverse=True)

    def test_to_dict(self):
        df = _toy_df()
        out = drill_down(
            df,
            metric_col="metric",
            dimension="region",
            parent_value="US",
            child_dimension="device",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        d = out.to_dict()
        assert "slices" in d
        assert "top_drivers" in d

    def test_missing_columns_raises(self):
        df = _toy_df().drop(columns=["region"])
        with pytest.raises(ValueError):
            drill_down(
                df,
                metric_col="metric",
                dimension="region",
                parent_value="EU",
                child_dimension="device",
                baseline_window={"query": "month == 'A'"},
                current_window={"query": "month == 'B'"},
            )


# ---------------------------------------------------------------------------
# Narrative
# ---------------------------------------------------------------------------


class TestNarrative:
    def test_increased_significantly(self):
        # Use the clean fixture so the top driver is reproducible.
        df = pd.DataFrame(
            {
                "month": ["A"] * 30 + ["B"] * 30,
                "region": (["EU"] * 10 + ["US"] * 10 + ["APAC"] * 10) * 2,
                "metric": (
                    [10.0] * 30
                    + [15.0] * 10 + [7.0] * 10 + [10.0] * 10
                ),
            }
        )
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        out = render_narrative(res, kpi_name="Churn Rate")
        assert "Churn Rate" in out
        # Top driver EU should appear in the narrative.
        assert "EU" in out

    def test_decreased(self):
        # Build a scenario where the metric went down.
        rng = np.random.RandomState(1)
        df = pd.DataFrame(
            {
                "month": ["A"] * 50 + ["B"] * 50,
                "region": ["X"] * 100,
                "metric": list(rng.normal(20, 1, 50)) + list(rng.normal(5, 1, 50)),
            }
        )
        res = waterfall(
            df,
            metric_col="metric",
            dimension="region",
            baseline_window={"query": "month == 'A'"},
            current_window={"query": "month == 'B'"},
        )
        out = render_narrative(res)
        assert "decreased" in out
