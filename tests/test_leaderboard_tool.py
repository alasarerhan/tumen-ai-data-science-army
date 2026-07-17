"""Tests for I3 Experiment Tracking / Leaderboard tool."""
from __future__ import annotations

import math

import pytest

import ai_data_science_team.tools.leaderboard as i3


@pytest.fixture
def store():
    return i3.ExperimentStore()


@pytest.fixture
def populated_store():
    s = i3.ExperimentStore()
    for i, m_id in enumerate(["rf", "xgb", "lr"]):
        i3.record_run(
            s,
            experiment_id="exp1",
            model_id=m_id,
            metrics={"auc": 0.7 + 0.05 * i, "f1": 0.5 + 0.05 * i,
                     "rmse": 1.0 - 0.1 * i},
            params={"depth": 3 + i},
            is_champion=(m_id == "xgb"),
            created_at=100.0 + i,
        )
    i3.record_run(
        s, experiment_id="exp2", model_id="rf",
        metrics={"auc": 0.6}, created_at=200.0,
    )
    return s


class TestRecordRun:
    def test_record_run_returns_dataclass(self, store):
        rec = i3.record_run(
            store, experiment_id="e1", model_id="m1",
            metrics={"auc": 0.8},
        )
        assert isinstance(rec, i3.ExperimentRecord)
        assert rec.experiment_id == "e1"
        assert rec.metrics["auc"] == 0.8
        assert rec.run_id != ""

    def test_record_run_with_custom_run_id(self, store):
        rec = i3.record_run(
            store, experiment_id="e1", model_id="m1",
            metrics={"auc": 0.7}, run_id="custom-id",
        )
        assert rec.run_id == "custom-id"


class TestStore:
    def test_by_experiment_filters(self, populated_store):
        rows = populated_store.by_experiment("exp1")
        assert len(rows) == 3
        assert all(r.experiment_id == "exp1" for r in rows)

    def test_by_model_filters(self, populated_store):
        rows = populated_store.by_model("rf")
        assert len(rows) == 2


class TestLeaderboard:
    def test_leaderboard_ranks_descending(self, populated_store):
        entries = i3.leaderboard(populated_store, "exp1", "auc")
        assert [e.rank for e in entries] == [1, 2, 3]
        assert entries[0].model_id == "lr"
        assert pytest.approx(entries[0].primary_value, abs=1e-9) == 0.8
        assert entries[1].model_id == "xgb"
        assert pytest.approx(entries[1].primary_value, abs=1e-9) == 0.75
        assert entries[2].model_id == "rf"
        assert pytest.approx(entries[2].primary_value, abs=1e-9) == 0.7

    def test_leaderboard_top_k(self, populated_store):
        entries = i3.leaderboard(populated_store, "exp1", "auc", top_k=2)
        assert len(entries) == 2

    def test_leaderboard_model_filter(self, populated_store):
        entries = i3.leaderboard(
            populated_store, "exp1", "auc",
            model_filter=["rf", "xgb"],
        )
        assert {e.model_id for e in entries} == {"rf", "xgb"}

    def test_leaderboard_higher_is_better_false(self, populated_store):
        entries = i3.leaderboard(
            populated_store, "exp1", "rmse", higher_is_better=False,
        )
        assert pytest.approx(entries[0].primary_value, abs=1e-9) == 0.8

    def test_leaderboard_delta_to_champion(self, populated_store):
        entries = i3.leaderboard(populated_store, "exp1", "auc")
        champion_entry = next(e for e in entries if e.delta_to_champion is None)
        assert champion_entry.model_id == "xgb"
        # lr has auc=0.8 > champion 0.75 → positive delta
        # rf has auc=0.7 < champion 0.75 → negative delta
        deltas = {e.model_id: e.delta_to_champion for e in entries}
        assert deltas["lr"] is not None and deltas["lr"] > 0
        assert deltas["rf"] is not None and deltas["rf"] < 0

    def test_leaderboard_unknown_metric(self, populated_store):
        entries = i3.leaderboard(populated_store, "exp1", "accuracy")
        assert entries == []

    def test_leaderboard_unknown_experiment(self, populated_store):
        assert i3.leaderboard(populated_store, "nope", "auc") == []


class TestSummariseMetrics:
    def test_basic_stats(self, populated_store):
        s = i3.summarise_metrics(populated_store, "exp1", "auc")
        assert s["n"] == 3
        assert 0.7 <= s["mean"] <= 0.8
        assert pytest.approx(s["min"], abs=1e-9) == 0.7
        assert pytest.approx(s["max"], abs=1e-9) == 0.8

    def test_empty_experiment(self, store):
        s = i3.summarise_metrics(store, "e1", "auc")
        assert s["n"] == 0.0
        assert math.isnan(s["mean"])

    def test_single_value_std_zero(self, store):
        i3.record_run(
            store, experiment_id="e1", model_id="m",
            metrics={"auc": 0.5},
        )
        s = i3.summarise_metrics(store, "e1", "auc")
        assert s["std"] == 0.0


class TestParallelCoordinates:
    def test_payload_shape(self, populated_store):
        payload = i3.parallel_coordinates_payload(
            populated_store, "exp1", ["auc", "f1", "rmse"],
        )
        assert payload["experiment_id"] == "exp1"
        assert payload["metrics"] == ["auc", "f1", "rmse"]
        assert len(payload["points"]) == 3

    def test_payload_missing_metric_nan(self, store):
        i3.record_run(
            store, experiment_id="e1", model_id="m",
            metrics={"auc": 0.7},
        )
        payload = i3.parallel_coordinates_payload(
            store, "e1", ["auc", "f1"],
        )
        assert payload["points"][0]["f1"] != payload["points"][0]["f1"]  # NaN

