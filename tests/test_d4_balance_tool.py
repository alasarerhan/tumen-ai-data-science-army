"""Tests for D4 Imbalanced Data tool."""
from __future__ import annotations

import math

import pytest

import ai_data_science_team.tools.d4_balance as d4


class TestClassDistribution:
    def test_basic(self):
        y = [0] * 80 + [1] * 20
        d = d4.class_distribution(y)
        assert d.n == 100
        assert d.n_classes == 2
        assert d.majority_count == 80
        assert d.minority_count == 20
        assert d.imbalance_ratio == 4.0

    def test_balanced(self):
        y = [0] * 50 + [1] * 50
        d = d4.class_distribution(y)
        assert d.imbalance_ratio == 1.0

    def test_three_classes(self):
        y = [0] * 100 + [1] * 50 + [2] * 10
        d = d4.class_distribution(y)
        assert d.n_classes == 3
        assert d.imbalance_ratio == 10.0

    def test_empty(self):
        d = d4.class_distribution([])
        assert d.n == 0
        assert d.imbalance_ratio == 1.0

    def test_single_class(self):
        d = d4.class_distribution([0, 0, 0])
        assert d.n_classes == 1


class TestIsImbalanced:
    def test_balanced(self):
        d = d4.class_distribution([0] * 50 + [1] * 50)
        v = d4.is_imbalanced(d)
        assert v["is_imbalanced"] is False
        assert v["severity"] == "balanced"

    def test_moderate(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        v = d4.is_imbalanced(d)
        assert v["is_imbalanced"] is True
        assert v["severity"] == "moderate"

    def test_severe(self):
        d = d4.class_distribution([0] * 990 + [1] * 10)
        v = d4.is_imbalanced(d)
        assert v["is_imbalanced"] is True
        assert v["severity"] == "severe"


class TestSelectStrategy:
    def test_balanced_returns_none(self):
        d = d4.class_distribution([0] * 50 + [1] * 50)
        s = d4.select_strategy(d)
        assert s["primary"] == "none"

    def test_severe_picks_smote(self):
        d = d4.class_distribution([0] * 990 + [1] * 10)
        s = d4.select_strategy(d)
        assert s["primary"] == "smote"
        assert "class_weight" in s["alternatives"]

    def test_severe_without_synthetic(self):
        d = d4.class_distribution([0] * 990 + [1] * 10)
        s = d4.select_strategy(d, has_synthetic_capability=False)
        assert s["primary"] == "class_weight"

    def test_moderate_picks_class_weight(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        s = d4.select_strategy(d)
        assert s["primary"] == "class_weight"

    def test_small_dataset_downweights_undersampling(self):
        # imbalanced but small → class_weight still wins
        d = d4.class_distribution([0] * 80 + [1] * 20)
        s = d4.select_strategy(d, dataset_size=1000)
        assert s["primary"] != "undersampling"

    def test_large_dataset_can_undersample(self):
        d = d4.class_distribution([0] * 8000 + [1] * 2000)
        s = d4.select_strategy(d)
        # both class_weight and undersampling plausible; primary
        # should be one of the candidates
        assert s["primary"] in ("class_weight", "threshold_tuning",
                                "smote", "undersampling")

    def test_interpretability_preference(self):
        d = d4.class_distribution([0] * 990 + [1] * 10)
        s_default = d4.select_strategy(d)
        s_interp = d4.select_strategy(d, prefers_interpretability=True)
        # interpretability should not change severe → smote is still
        # chosen when IR is very high; check at least one boost
        assert "class_weight" in s_interp["alternatives"]


class TestEstimateStrategyImpact:
    def test_smote_resizes_minority_to_majority(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        impact = d4.estimate_strategy_impact(d, "smote")
        assert impact["effective"] is True
        assert impact["after"]["n"] == 160  # + 60 synth
        assert impact["after"]["imbalance_ratio"] == 1.0

    def test_undersampling_trims_majority(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        impact = d4.estimate_strategy_impact(d, "undersampling")
        assert impact["effective"] is True
        assert impact["after"]["n"] == 40  # 20 + 20
        assert impact["after"]["imbalance_ratio"] == 1.0

    def test_class_weight_keeps_n(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        impact = d4.estimate_strategy_impact(d, "class_weight")
        assert impact["effective"] is False
        assert "weights" in impact["after"]
        # weight for class 1 should be > weight for class 0
        w0 = impact["after"]["weights"][0]
        w1 = impact["after"]["weights"][1]
        assert w1 > w0

    def test_threshold_tuning_keeps_n(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        impact = d4.estimate_strategy_impact(d, "threshold_tuning")
        assert impact["effective"] is False
        assert impact["after"]["n"] == d.n

    def test_invalid_strategy(self):
        d = d4.class_distribution([0] * 80 + [1] * 20)
        with pytest.raises(ValueError):
            d4.estimate_strategy_impact(d, "magic")


class TestRecommendMetrics:
    def test_imbalanced_recommends_pr_auc(self):
        d = d4.class_distribution([0] * 990 + [1] * 10)
        rec = d4.recommend_metrics(d)
        assert rec.primary_metric == "pr_auc"
        assert "roc_auc" in rec.secondary_metrics

    def test_balanced_recommends_accuracy(self):
        d = d4.class_distribution([0] * 50 + [1] * 50)
        rec = d4.recommend_metrics(d)
        assert rec.primary_metric == "accuracy"


class TestUndersampleIndices:
    def test_balances_to_ratio(self):
        y = [0] * 80 + [1] * 20
        idx = d4.undersample_indices(y, target_ratio=1.0,
                                       random_state=0)
        kept = [y[i] for i in idx]
        assert len(idx) == 40  # 20 majority + 20 minority
        assert kept.count(0) == kept.count(1) == 20

    def test_target_ratio_2(self):
        y = [0] * 80 + [1] * 20
        idx = d4.undersample_indices(y, target_ratio=2.0,
                                       random_state=0)
        kept = [y[i] for i in idx]
        # 40 majority + 20 minority = 60
        assert len(idx) == 60
        assert kept.count(0) == 40
        assert kept.count(1) == 20

    def test_empty(self):
        assert d4.undersample_indices([]) == []

    def test_single_class(self):
        idx = d4.undersample_indices([0, 0, 0, 0])
        assert idx == [0, 1, 2, 3]


class TestClassWeight:
    def test_inverse_frequency(self):
        y = [0] * 80 + [1] * 20
        w = d4.class_weight(y)
        # inverse-frequency: minority gets higher weight
        assert w[0] < w[1]
        # exact scikit-learn-style values:
        # w[c] = n / (n_classes * count[c])
        # w[0] = 100 / (2 * 80) = 0.625
        # w[1] = 100 / (2 * 20) = 2.5
        assert math.isclose(w[0], 0.625, abs_tol=1e-9)
        assert math.isclose(w[1], 2.5, abs_tol=1e-9)

    def test_balanced_uniform(self):
        y = [0] * 50 + [1] * 50
        w = d4.class_weight(y)
        assert math.isclose(w[0], w[1], abs_tol=1e-9)

    def test_empty(self):
        assert d4.class_weight([]) == {}


class TestApplyStrategy:
    def test_undersampling_kept_indices(self):
        y = [0] * 80 + [1] * 20
        r = d4.apply_strategy(y, "undersampling", random_state=0)
        assert r.original_n == 100
        assert r.resampled_n == 40
        assert all(y[i] in (0, 1) for i in r.kept_indices)

    def test_class_weight_keeps_all(self):
        y = [0] * 80 + [1] * 20
        r = d4.apply_strategy(y, "class_weight")
        assert r.resampled_n == 100
        assert r.kept_indices == list(range(100))

    def test_smote_keeps_all(self):
        y = [0] * 80 + [1] * 20
        r = d4.apply_strategy(y, "smote")
        assert r.resampled_n == 100  # SMOTE synthesises separately

    def test_invalid_strategy(self):
        with pytest.raises(ValueError):
            d4.apply_strategy([0, 1], "magic")


class TestBalancePayload:
    def test_full_payload(self):
        d = d4.class_distribution([0] * 990 + [1] * 10)
        p = d4.balance_payload(d)
        assert "distribution" in p
        assert "verdict" in p
        assert "selected_strategy" in p
        assert "rationale" in p
        assert "impact" in p
        assert "recommended_metrics" in p
        assert p["recommended_metrics"]["primary"] == "pr_auc"
        assert p["selected_strategy"] == "smote"

    def test_payload_json_safe(self):
        import json
        d = d4.class_distribution([0] * 990 + [1] * 10)
        p = d4.balance_payload(d)
        json.dumps(p)  # must not raise


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = d4.D4_BALANCE_TOOL_NAMES
        for n in ("d4_class_distribution", "d4_is_imbalanced",
                  "d4_select_strategy", "d4_estimate_strategy_impact",
                  "d4_recommend_metrics", "d4_undersample_indices",
                  "d4_class_weight", "d4_apply_strategy",
                  "d4_balance_payload"):
            assert n in names
