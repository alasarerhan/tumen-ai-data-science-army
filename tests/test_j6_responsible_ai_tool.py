"""Tests for J6 Responsible AI Dashboard tool."""
from __future__ import annotations

import pytest

import ai_data_science_team.tools.j6_responsible_ai as j6


class TestComputeFairness:
    def test_balanced_groups_no_violation(self):
        # balanced: both groups have same selection rate
        report = j6.compute_fairness(
            protected_attribute="gender",
            group_labels=["M"] * 50 + ["F"] * 50,
            y_true=[1] * 30 + [0] * 20 + [1] * 30 + [0] * 20,
            y_pred=[1] * 25 + [0] * 25 + [1] * 25 + [0] * 25,
            threshold=0.05,
        )
        assert report.violations == []

    def test_imbalanced_groups_violation(self):
        # M selected 80%, F selected 20% → DP diff 0.6 > threshold
        report = j6.compute_fairness(
            protected_attribute="gender",
            group_labels=["M"] * 50 + ["F"] * 50,
            y_true=[1] * 40 + [0] * 10 + [1] * 40 + [0] * 10,
            y_pred=[1] * 40 + [0] * 10 + [1] * 10 + [0] * 40,
            threshold=0.10,
        )
        assert report.demographic_parity_diff > 0.5
        assert any("demographic_parity" in v for v in report.violations)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            j6.compute_fairness(
                protected_attribute="g",
                group_labels=["M", "F"],
                y_true=[1, 0, 1], y_pred=[1, 0],
            )


class TestComputeExplainability:
    def test_top_k_ordering(self):
        rep = j6.compute_explainability(
            feature_names=["a", "b", "c", "d"],
            shap_abs_means=[0.1, 0.5, 0.3, 0.2],
            top_k=3,
        )
        assert rep.contributions[0].feature == "b"
        assert rep.contributions[0].global_importance_rank == 1
        # top-3 by descending mean_abs_shap: b(0.5), c(0.3), d(0.2)
        assert rep.contributions[1].feature == "c"
        assert rep.contributions[1].global_importance_rank == 2
        assert rep.contributions[2].feature == "d"
        assert rep.contributions[2].global_importance_rank == 3
        assert len(rep.contributions) == 3

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            j6.compute_explainability(
                feature_names=["a", "b"],
                shap_abs_means=[0.1, 0.2, 0.3],
            )


class TestDiscoverErrorSlices:
    def test_finds_worst_slice(self):
        # baseline error rate ~30%; tenure<3 has much higher error
        n = 200
        y_true = [1] * n
        y_pred = [1] * 130 + [0] * 70  # 70/200 = 35% error
        feature_values = {
            "tenure": ["<3"] * 50 + [">=3"] * 150,
            "region": ["A"] * 100 + ["B"] * 100,
        }
        # make tenure<3 errors very high
        y_pred_t = list(y_pred)
        for i in range(50):  # tenure<3 group
            y_pred_t[i] = 0  # all wrong
        slices = j6.discover_error_slices(
            y_true=y_true, y_pred=y_pred_t,
            feature_values=feature_values,
            min_slice_n=10,
        )
        assert slices
        # tenure<3 should be top
        assert slices[0].slice_expr.startswith("tenure")
        assert slices[0].lift > 0

    def test_no_lift_no_slice(self):
        y_true = [1] * 100
        # All groups share same 30% error rate → no lift → no slice
        y_pred = ([0] * 15 + [1] * 35) * 2  # each 50-sample group has 15 errors
        slices = j6.discover_error_slices(
            y_true=y_true, y_pred=y_pred,
            feature_values={"x": ["a"] * 50 + ["b"] * 50},
            min_slice_n=10,
        )
        assert slices == []

    def test_min_slice_n_filters(self):
        y_true = [1] * 100
        y_pred = [0] * 100
        slices = j6.discover_error_slices(
            y_true=y_true, y_pred=y_pred,
            feature_values={"x": ["a"] * 5 + ["b"] * 95},
            min_slice_n=10,
        )
        # "a" group has only 5 samples, filtered out
        assert all(s.slice_expr != "x='a'" for s in slices)


class TestSuggestMitigations:
    def test_no_violations_no_action(self):
        out = j6.suggest_mitigations(None, [])
        assert out == ["No mitigations required."]

    def test_violation_includes_reweighing(self):
        fair = j6.compute_fairness(
            protected_attribute="gender",
            group_labels=["M"] * 50 + ["F"] * 50,
            y_true=[1] * 40 + [0] * 10 + [1] * 40 + [0] * 10,
            y_pred=[1] * 40 + [0] * 10 + [1] * 10 + [0] * 40,
        )
        out = j6.suggest_mitigations(fair, [])
        assert any("reweighing" in s.lower() for s in out)

    def test_error_slices_includes_investigate(self):
        fair = j6.compute_fairness(
            protected_attribute="gender",
            group_labels=["M"] * 50 + ["F"] * 50,
            y_true=[1] * 40 + [0] * 10 + [1] * 40 + [0] * 10,
            y_pred=[1] * 40 + [0] * 10 + [1] * 10 + [0] * 40,
        )
        slice_ = j6.discover_error_slices(
            y_true=[1] * 200,
            y_pred=[0] * 50 + [1] * 150,
            feature_values={"tenure": ["<3"] * 50 + [">=3"] * 150},
            min_slice_n=10,
        )
        out = j6.suggest_mitigations(fair, slice_)
        assert any("Investigate slice" in s for s in out)


class TestBuildDashboard:
    def test_minimal_dashboard(self):
        d = j6.build_dashboard(model_id="m1")
        assert d.model_id == "m1"
        assert d.fairness is None
        assert d.explainability is None
        assert d.error_slices == []
        assert d.violations == []

    def test_payload_round_trip_json(self):
        import json
        d = j6.build_dashboard(model_id="m1")
        p = j6.dashboard_payload(d)
        json.dumps(p)  # must not raise


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = j6.J6_RESPONSIBLE_AI_TOOL_NAMES
        for n in ("j6_compute_fairness", "j6_compute_explainability",
                  "j6_discover_error_slices", "j6_suggest_mitigations",
                  "j6_build_dashboard", "j6_dashboard_payload"):
            assert n in names
