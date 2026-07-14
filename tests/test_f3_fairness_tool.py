"""Tests for ``ai_data_science_team.tools.f3_fairness`` (F3 tool layer)."""

from __future__ import annotations

import numpy as np
import pandas as pd

import ai_data_science_team.tools.f3_fairness as f3


def _toy():
    rng = np.random.RandomState(0)
    n = 200
    group = rng.choice(["A", "B"], size=n)
    # A gets predicted positive 50% of the time, B 30%.
    base = rng.uniform(size=n)
    p = 0.5 * (group == "A") + 0.3 * (group == "B") + 0.2 * (base > 0.5)
    y_pred = (rng.uniform(size=n) < p).astype(int)
    y_true = (rng.uniform(size=n) < 0.5).astype(int)
    y_proba = 0.5 + 0.5 * p
    return y_true, y_pred, group, y_proba


class TestPerGroupMetrics:
    def test_basic(self):
        y_true, y_pred, g, _ = _toy()
        df = f3.per_group_metrics(y_true, y_pred, g)
        assert set(df["group"]) == {"A", "B"}
        assert {"selection_rate", "tpr", "fpr", "n"} <= set(df.columns)


class TestAggregateMetrics:
    def test_dp_difference_is_range(self):
        y_true, y_pred, g, _ = _toy()
        df = f3.per_group_metrics(y_true, y_pred, g)
        dpd = f3.demographic_parity_difference(df)
        dpr = f3.demographic_parity_ratio(df)
        eod = f3.equalized_odds_difference(df)
        assert 0 <= dpd <= 1
        assert 0 <= dpr <= 1
        assert 0 <= eod <= 1


class TestFourFifths:
    def test_violation_flagged(self):
        y_true, y_pred, g, _ = _toy()
        df = f3.per_group_metrics(y_true, y_pred, g)
        v = f3.violates_four_fifths(df, threshold=0.8)
        assert "A" in v and "B" in v

    def test_no_violation_when_above_threshold(self):
        y_true = [1, 0, 1, 0]
        y_pred = [1, 0, 1, 0]
        g = ["X", "X", "Y", "Y"]
        df = f3.per_group_metrics(y_true, y_pred, g)
        v = f3.violates_four_fifths(df, threshold=0.5)
        assert not any(v.values())


class TestMitigation:
    def test_returns_per_group_threshold(self):
        y_true, y_pred, g, y_proba = _toy()
        df = f3.simulate_threshold_mitigation(y_true, y_proba, g)
        assert set(df["group"]) == {"A", "B"}
        assert (df["selection_rate"] >= 0).all()
        assert (df["selection_rate"] <= 1).all()

    def test_target_rate(self):
        y_true = [1, 0, 1, 0]
        y_proba = [0.9, 0.7, 0.6, 0.4]
        g = ["A", "A", "B", "B"]
        df = f3.simulate_threshold_mitigation(
            y_true, y_proba, g, target_rate=0.5,
        )
        # 50% selection rate ⇒ each group gets 1 positive.
        assert (df["selection_rate"] == 0.5).all()


class TestAuditFairness:
    def test_basic_report(self):
        y_true, y_pred, g, _ = _toy()
        rep = f3.audit_fairness(y_true, y_pred, g, sensitive_column="region")
        assert isinstance(rep.group_metrics, pd.DataFrame)
        d = rep.to_dict()
        assert "group_metrics" in d
        assert "dp_difference" in d
        assert "dp_ratio" in d
        assert "eod" in d
        assert "four_fifths_violations" in d
        assert "recommendations" in d

    def test_no_violation_clean_data(self):
        y_true = [1, 0, 1, 0, 1, 0, 1, 0]
        y_pred = [1, 0, 1, 0, 1, 0, 1, 0]
        g = ["X", "X", "X", "X", "Y", "Y", "Y", "Y"]
        rep = f3.audit_fairness(y_true, y_pred, g)
        assert not any(rep.four_fifths_violations.values())
        assert not rep.recommendations or all(
            "No fairness issues" in r
            or "violated" not in r
            for r in rep.recommendations
        )

    def test_with_proba_mitigation(self):
        y_true, y_pred, g, y_proba = _toy()
        rep = f3.audit_fairness(
            y_true, y_pred, g, y_proba=y_proba,
        )
        assert rep.mitigated is not None

