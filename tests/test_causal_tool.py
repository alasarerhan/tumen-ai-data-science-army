"""
Tests for ``ai_data_science_team.tools.causal`` (A5 tool layer).
"""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.tools.causal import (
    adj_lift,
    check_propensity_overlap,
    did_lift,
    e_value,
)


class TestDidLift:
    def test_basic_di_d_estimate(self):
        # 50 treated + 50 control; +5 in control pre→post (secular trend),
        # +10 in treated pre→post — DiD = 5.
        rng = np.random.RandomState(0)
        pre_t_pre = rng.normal(size=50, loc=10)
        pre_t_post = pre_t_pre + 10  # +10 lifted
        ctl_pre = rng.normal(size=50, loc=8)
        ctl_post = ctl_pre + 5  # +5 secular
        out = did_lift(pre_t_pre.tolist(), pre_t_post.tolist(), ctl_pre.tolist(), ctl_post.tolist())
        assert abs(out["ate"] - 5.0) < 0.01
        assert out["n_treated"] == 50
        assert out["n_control"] == 50


class TestAdjLift:
    def test_ate_recovered_with_unrelated_covariate(self):
        rng = np.random.RandomState(0)
        n = 200
        t = rng.binomial(1, 0.5, size=n)
        cov = rng.normal(size=n)
        y = 2.0 * t + 0.0 * cov + rng.normal(size=n) * 0.5
        # Pass the single covariate as a 1-D sequence (the documented
        # public contract).  Tool reshapes internally.
        out = adj_lift(y.tolist(), t.tolist(), cov.tolist())
        assert abs(out["ate"] - 2.0) < 0.4

    def test_invalid_treatment_raises(self):
        with pytest.raises(ValueError):
            adj_lift([0, 1, 0], [0, 1, 2], [[0.1]])


class TestPropensityOverlap:
    def test_quantiles_reported(self):
        rng = np.random.RandomState(0)
        ps = rng.uniform(size=100)
        out = check_propensity_overlap(ps)
        assert "treatment" in out
        assert out["overlap_ok"] is True
        q = out["treatment"]
        assert q["q05"] < q["q25"] < q["q50"] < q["q75"] < q["q95"]

    def test_extreme_propensity_warns(self):
        # Half of them have p < 0.05 — overlap_ok should be False.
        ps = [0.01] * 50 + [0.5] * 50
        out = check_propensity_overlap(ps)
        assert out["overlap_ok"] is False
        assert out["share_extreme_low"] > 0.10


class TestEValue:
    def test_perfect_estimate(self):
        # OR = 2 → expected E-value ≈ 3.41
        assert abs(e_value(2.0) - 3.41) < 0.05

    def test_unit_estimate_returns_one(self):
        assert e_value(1.0) == 1.0

    def test_sub_unit_estimate_inverts(self):
        # 0.5 → invert to 2.0 → same E-value.
        a = e_value(0.5)
        b = e_value(2.0)
        assert abs(a - b) < 1e-6
