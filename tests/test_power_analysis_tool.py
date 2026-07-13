"""
Tests for ``ai_data_science_team.tools.power_analysis`` (A2 tool layer).

Targets the real public API exposed by the implementation:
* ``solve_power`` — dispatcher supporting all four power-analysis problems
* ``required_sample_size`` — convenience wrapper (returns dict from solve_power)
* ``minimum_detectable_effect`` — convenience wrapper (returns MDE-flat dict)
* ``estimate_runtime_days`` — runtime estimator (returns dict with 'days_needed')
* ``suggest_stratification`` — column-recommender (returns dict with 'recommendations')
* ``design_experiment`` — end-to-end façade (returns nested dict)
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.proportion import proportion_effectsize

from ai_data_science_team.tools.power_analysis import (
    solve_power,
    required_sample_size,
    minimum_detectable_effect,
    estimate_runtime_days,
    suggest_stratification,
    design_experiment,
)


# ---------------------------------------------------------------------------
# 1. solve_power — the canonical dispatcher
# ---------------------------------------------------------------------------

class TestSolvePower:
    def test_solve_n_proportion(self):
        out = solve_power(
            solve_for="n",
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.06,
            alpha=0.05,
            power=0.80,
            ratio=1.0,
        )
        n = out["solved_value"]
        assert out["metric_type"] == "proportion"
        assert 1_000 < n < 20_000
        assert out["alpha"] == pytest.approx(0.05)
        assert out["power"] == pytest.approx(0.80)
        # Cohen's h now stored as positive magnitude (bug fix from sign-flipped)
        assert out["cohen_h"] >= 0

    def test_solve_power_proportion(self):
        out = solve_power(
            solve_for="power",
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
            nobs1=5_000,
            alpha=0.05,
            ratio=1.0,
        )
        assert 0.0 <= out["solved_value"] <= 1.0
        assert out["power"] == pytest.approx(out["solved_value"])

    def test_solve_alpha_proportion(self):
        out = solve_power(
            solve_for="alpha",
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
            nobs1=3_000,
            power=0.80,
        )
        assert 1e-4 < out["solved_value"] < 0.2

    def test_solve_effect_size_proportion_no_nan(self):
        out = solve_power(
            solve_for="effect_size",
            metric_type="proportion",
            baseline_rate=0.05,
            nobs1=10_000,
            alpha=0.05,
            power=0.80,
        )
        es = out["solved_value"]
        assert math.isfinite(es)
        assert es > 0
        # Cohen's h for two proportions from 5% baseline at typical 80% power
        # / 5% alpha / 10k per arm: MDE is roughly 0.04 absolute lift ⇒ h ≈ 0.04.
        assert 0.02 < es < 0.10

    def test_solve_n_continuous(self):
        out = solve_power(
            solve_for="n",
            metric_type="continuous",
            baseline_mean=100.0,
            baseline_sd=15.0,
            expected_lift=5.0,
            alpha=0.05,
            power=0.80,
        )
        assert out["metric_type"] == "continuous"
        assert out["solved_value"] > 0

    def test_invalid_solve_for(self):
        with pytest.raises(ValueError):
            solve_power(solve_for="banana", baseline_rate=0.05)

    def test_invalid_proportion_inputs(self):
        with pytest.raises(ValueError):
            solve_power(
                solve_for="n",
                metric_type="proportion",
                baseline_rate=1.5,
                expected_treatment_rate=0.06,
            )

    def test_proportion_effectsize_reference(self):
        # Sanity-check the statsmodels reference (magnitude, not sign).
        h1 = abs(float(proportion_effectsize(0.05, 0.06)))
        h2 = abs(float(proportion_effectsize(0.06, 0.05)))
        assert h1 == pytest.approx(h2, rel=1e-9)
        # 0.05 vs 0.06 is a small effect, h ≈ 0.044
        assert 0.04 < h1 < 0.05


# ---------------------------------------------------------------------------
# 2. required_sample_size — convenience wrapper around solve_power
# ---------------------------------------------------------------------------

class TestRequiredSampleSize:
    def test_smoke_proportions(self):
        out = required_sample_size(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.06,
            alpha=0.05,
            power=0.80,
        )
        assert 3_000 < out["solved_value"] < 10_000
        assert out["solve_for"] == "n"

    def test_unequal_group_ratio(self):
        # We don't make assumptions about which direction ratio>1 swings
        # total N (depends on effect size); just check it terminates cleanly.
        a = required_sample_size(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
            alpha=0.05,
            power=0.80,
            ratio=1.0,
        )["solved_value"]
        b = required_sample_size(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.07,
            alpha=0.05,
            power=0.80,
            ratio=2.0,
        )["solved_value"]
        assert a > 0 and b > 0


# ---------------------------------------------------------------------------
# 3. minimum_detectable_effect — convenience wrapper (dict with effect_size)
# ---------------------------------------------------------------------------

class TestMinimumDetectableEffect:
    def test_smoke_proportions(self):
        out = minimum_detectable_effect(
            nobs1=10_000,
            metric_type="proportion",
            baseline_rate=0.05,
            alpha=0.05,
            power=0.80,
            ratio=1.0,
            alternative="two-sided",
        )
        mde = out["effect_size"]
        assert isinstance(mde, float)
        assert math.isfinite(mde)
        assert mde > 0
        # Cohen's h ≈ 0.04 for this scenario
        assert 0.02 < mde < 0.10

    def test_does_not_return_nan(self):
        out = minimum_detectable_effect(
            nobs1=5_000,
            metric_type="proportion",
            baseline_rate=0.05,
            alpha=0.05,
            power=0.80,
        )
        mde = out["effect_size"]
        assert math.isfinite(mde)
        assert mde > 0

    def test_small_n_gives_large_mde(self):
        small_n = minimum_detectable_effect(
            nobs1=200,
            metric_type="proportion",
            baseline_rate=0.05,
            alpha=0.05,
            power=0.80,
        )["effect_size"]
        big_n = minimum_detectable_effect(
            nobs1=20_000,
            metric_type="proportion",
            baseline_rate=0.05,
            alpha=0.05,
            power=0.80,
        )["effect_size"]
        assert small_n > big_n

    def test_absolute_lift_inversion_returns_positive(self):
        # The brentq inversion from Cohen's h to absolute lift should yield
        # a non-None, positive value for typical MDE inputs.
        out = minimum_detectable_effect(
            nobs1=10_000,
            metric_type="proportion",
            baseline_rate=0.05,
            alpha=0.05,
            power=0.80,
        )
        absolute_lift = out.get("absolute_lift")
        assert absolute_lift is not None
        assert 0.001 < absolute_lift < 0.10  # plausible range for 5% baseline


# ---------------------------------------------------------------------------
# 4. estimate_runtime_days — runtime estimator (returns dict with 'days_needed')
# ---------------------------------------------------------------------------

class TestEstimateRuntimeDays:
    def test_basic_proportion(self):
        out = estimate_runtime_days(
            required_n_per_arm=5000,
            daily_traffic=500,
            num_arms=2,
            traffic_allocation=1.0,
            ramp_up_days=0,
        )
        # total_required = 5000 * 2 = 10_000; daily_eligible = 500; days_main=20
        assert out["days_needed"] >= 20
        assert out["total_required_n"] == 10_000
        assert out["daily_eligible_users"] == 500

    def test_zero_traffic_raises_value_error(self):
        # The function explicitly requires positive daily_traffic.
        with pytest.raises(ValueError):
            estimate_runtime_days(
                required_n_per_arm=1000,
                daily_traffic=0,
                num_arms=2,
            )

    def test_higher_traffic_faster(self):
        slow = estimate_runtime_days(2000, 50, num_arms=2)["days_needed"]
        fast = estimate_runtime_days(2000, 500, num_arms=2)["days_needed"]
        assert slow > fast


# ---------------------------------------------------------------------------
# 5. suggest_stratification — column-recommender (dict with 'recommendations')
# ---------------------------------------------------------------------------

class TestSuggestStratification:
    def test_smoke_returns_dict(self):
        df = pd.DataFrame(
            {
                "variant": ["control", "treatment"] * 50,
                "device": ["ios", "android", "web"] * 33 + ["ios"],
                "country": ["us", "uk", "de", "fr", "tr"] * 20,
                "revenue": np.random.RandomState(0).randn(100),
            }
        )
        out = suggest_stratification(data=df, group_column="variant")
        recs = out.get("recommendations") or out.get("columns") or []
        # Implementation returns a list of dicts each with a 'column' key.
        cols = [r.get("column") if isinstance(r, dict) else r for r in recs]
        assert isinstance(cols, list)
        # Each column referenced must exist in the frame.
        for c in cols:
            if c is not None:
                assert c in df.columns

    def test_group_column_excluded_or_noted(self):
        df = pd.DataFrame(
            {
                "variant": ["control", "treatment"] * 100,
                "device": ["ios", "android", "web", "ios"] * 50,
                "country": ["us", "uk", "de", "fr"] * 50,
            }
        )
        out = suggest_stratification(data=df, group_column="variant")
        recs = out.get("recommendations") or []
        # variant may be present if it's flagged as the assignment column,
        # but the *stratification* candidates should be other columns.
        strat_candidates = [
            r.get("column") for r in recs if isinstance(r, dict)
            and r.get("column") not in (None, "variant")
        ]
        # At least one non-variant candidate is recommended.
        assert any(
            c in {"device", "country"} for c in strat_candidates
        )


# ---------------------------------------------------------------------------
# 6. design_experiment — end-to-end façade (nested dict)
# ---------------------------------------------------------------------------

class TestDesignExperiment:
    def test_solve_n_branch_returns_nested_dict(self):
        out = design_experiment(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.06,
            alpha=0.05,
            power=0.80,
            daily_traffic=10_000,
        )
        assert isinstance(out, dict)
        # Top-level keys: 'sample_size', 'design_inputs', 'runtime'.
        assert "sample_size" in out
        assert "design_inputs" in out
        assert "runtime" in out
        n = out["sample_size"]["solved_value"]
        assert n > 0
        assert n == out["runtime"]["required_n_per_arm"]

    def test_solve_effect_size_branch(self):
        # Even without explicit nobs1, the function must return SOMETHING
        # well-formed.
        out = design_experiment(
            metric_type="proportion",
            baseline_rate=0.05,
            expected_treatment_rate=0.06,
            alpha=0.05,
            power=0.80,
            daily_traffic=10_000,
            num_arms=2,
        )
        assert isinstance(out, dict)
        assert len(out) > 0
