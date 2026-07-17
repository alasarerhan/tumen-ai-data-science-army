"""
Tests for ``ai_data_science_team.tools.modelops`` (K2 tool layer).
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.modelops import (
    STAGES,
    aggregate_registry_summary,
    build_model_detail,
    record_champion_change,
)


def _entry(model_id, version, stage="staging", is_champ=False, last_metric=None, promoted_at=None):
    return {
        "model_id": model_id,
        "version": version,
        "stage": stage,
        "is_champion": is_champ,
        "last_metric": last_metric,
        "promoted_at": promoted_at,
    }


class TestAggregateRegistry:
    def test_no_entries(self):
        result = aggregate_registry_summary([])
        assert result["stage_counts"] == {s: 0 for s in STAGES}
        assert result["champion"] is None
        assert result["n_models"] == 0

    def test_stage_counts(self):
        entries = [
            _entry("a", "1", stage="staging"),
            _entry("a", "2", stage="production"),
            _entry("b", "1", stage="production"),
            _entry("c", "1", stage="archived"),
        ]
        result = aggregate_registry_summary(entries)
        assert result["stage_counts"]["staging"] == 1
        assert result["stage_counts"]["production"] == 2
        assert result["stage_counts"]["archived"] == 1

    def test_champion_recorded_once(self):
        entries = [
            _entry("a", "1", stage="production", is_champ=True),
            _entry("a", "2", stage="staging", is_champ=True),
        ]
        result = aggregate_registry_summary(entries)
        # Only the first encountered champion is reported (one-active
        # policy); UI is responsible for surfacing duplicates.
        assert result["champion"]["model_id"] == "a"

    def test_drift_rollup(self):
        entries = [_entry("a", "1"), _entry("b", "1"), _entry("c", "1")]
        drift = {"a": "ok", "b": "warning", "c": "critical"}
        result = aggregate_registry_summary(entries, drift)
        assert result["drift_rollup"] == {"ok": 1, "warning": 1, "critical": 1}

    def test_entry_summary_shape(self):
        entries = [_entry("a", "1", stage="production", is_champ=True, last_metric=0.85)]
        result = aggregate_registry_summary(entries)
        s = result["entries"][0]
        for key in ("model_id", "version", "stage", "is_champion", "drift_status", "last_metric"):
            assert key in s


class TestBuildModelDetail:
    def test_basic_bundle(self):
        entry = _entry("a", "1", stage="production", is_champ=True, last_metric=0.9)
        bundle = build_model_detail(entry)
        d = bundle.to_dict()
        assert d["summary"]["model_id"] == "a"
        assert d["perf_snapshot"] is None
        assert d["drift_snapshot"] is None
        assert d["lineage_links"] == []
        assert d["retrain_policy_id"] is None
        assert d["champion_challenger_comparison_id"] is None

    def test_with_perf_drift_lineage(self):
        entry = _entry("a", "2")
        perf = {"metrics": {"roc_auc": 0.91}, "n_samples": 1000}
        drift = {"overall_drift": "moderate", "feature_heatmap": []}
        lineage = ["datawarehouse.public.users_v3"]
        bundle = build_model_detail(
            entry,
            perf_snapshot=perf,
            drift_snapshot=drift,
            lineage_links=lineage,
            retrain_policy_id="policy-x",
            champion_challenger_comparison_id="cmp-1",
        )
        d = bundle.to_dict()
        assert d["perf_snapshot"]["metrics"]["roc_auc"] == 0.91
        assert d["drift_snapshot"]["overall_drift"] == "moderate"
        assert d["lineage_links"] == lineage
        assert d["retrain_policy_id"] == "policy-x"
        assert d["champion_challenger_comparison_id"] == "cmp-1"

    def test_invalid_entry_raises(self):
        with pytest.raises(ValueError):
            build_model_detail("not-a-mapping")


class TestRecordChampionChange:
    def test_basic(self):
        out = record_champion_change("model-a", "1", "2")
        assert out["model_id"] == "model-a"
        assert out["previous_version"] == "1"
        assert out["new_version"] == "2"
        assert out["decided_by"] == "f2.promote"
        assert out["decided_at"] is None

    def test_first_promotion(self):
        out = record_champion_change("model-a", None, "1", decided_at="2026-07-13T10:00:00Z")
        assert out["previous_version"] is None
        assert out["decided_at"] == "2026-07-13T10:00:00Z"
