"""Tests for J4 Model Evaluation Store tool."""
from __future__ import annotations

import math

import pytest

import ai_data_science_team.tools.j4_eval_store as j4


@pytest.fixture
def store():
    return j4.EvalStore()


@pytest.fixture
def populated_store():
    s = j4.EvalStore()
    for ds_idx, ds in enumerate(["train", "test"]):
        for m_idx, m_id in enumerate(["rf", "xgb", "lr"]):
            j4.record_evaluation(
                s,
                model_id=m_id,
                dataset_id=ds,
                metrics={"auc": 0.7 + 0.05 * m_idx,
                         "f1": 0.5 + 0.03 * m_idx},
                slices=[
                    {"slice_name": "gender=M",
                     "metrics": {"auc": 0.71 + 0.02 * m_idx},
                     "sample_size": 1000},
                    {"slice_name": "gender=F",
                     "metrics": {"auc": 0.69 + 0.01 * m_idx},
                     "sample_size": 1100},
                ],
                created_at=100.0 + ds_idx * 10 + m_idx,
            )
    return s


class TestRecordEvaluation:
    def test_returns_dataclass(self, store):
        rec = j4.record_evaluation(
            store, model_id="m", dataset_id="d",
            metrics={"auc": 0.8},
        )
        assert isinstance(rec, j4.EvalRecord)
        assert rec.model_id == "m"
        assert rec.notes == ""
        assert rec.slices == []

    def test_slices_parsed(self, store):
        rec = j4.record_evaluation(
            store, model_id="m", dataset_id="d",
            metrics={"auc": 0.8},
            slices=[{"slice_name": "x", "metrics": {"auc": 0.7},
                     "sample_size": 50}],
        )
        assert len(rec.slices) == 1
        assert rec.slices[0].slice_name == "x"
        assert rec.slices[0].sample_size == 50

    def test_custom_eval_id(self, store):
        rec = j4.record_evaluation(
            store, model_id="m", dataset_id="d",
            metrics={"auc": 0.8}, eval_id="my-id",
        )
        assert rec.eval_id == "my-id"


class TestStoreAccessors:
    def test_by_model(self, populated_store):
        rows = populated_store.by_model("xgb")
        assert len(rows) == 2  # train + test

    def test_by_dataset(self, populated_store):
        rows = populated_store.by_dataset("train")
        assert len(rows) == 3


class TestQueryEvaluations:
    def test_filter_by_model_ids(self, populated_store):
        rows = j4.query_evaluations(populated_store, model_ids=["rf"])
        assert len(rows) == 2
        assert all(r.model_id == "rf" for r in rows)

    def test_filter_by_dataset_ids(self, populated_store):
        rows = j4.query_evaluations(populated_store, dataset_ids=["test"])
        assert len(rows) == 3

    def test_metric_range_filter(self, populated_store):
        rows = j4.query_evaluations(
            populated_store,
            metric_filter={"auc": (0.79, 1.0)},
        )
        # auc values: rf=0.7, xgb=0.75, lr=0.8 → only lr
        assert all(r.model_id == "lr" for r in rows)

    def test_combined_filter(self, populated_store):
        rows = j4.query_evaluations(
            populated_store,
            model_ids=["xgb", "lr"],
            dataset_ids=["train"],
        )
        assert len(rows) == 2


class TestCompareModels:
    def test_compare_two_models(self, populated_store):
        cmp = j4.compare_models(
            populated_store, ["rf", "xgb"], "train", ["auc", "f1"],
        )
        assert "rf" in cmp and "xgb" in cmp
        assert pytest.approx(cmp["rf"]["auc"], abs=1e-9) == 0.7
        assert pytest.approx(cmp["xgb"]["auc"], abs=1e-9) == 0.75

    def test_compare_requires_min_two(self, populated_store):
        with pytest.raises(ValueError):
            j4.compare_models(populated_store, ["rf"], "train", ["auc"])

    def test_compare_max_four(self, populated_store):
        with pytest.raises(ValueError):
            j4.compare_models(
                populated_store, ["a", "b", "c", "d", "e"], "train", ["auc"],
            )


class TestSummariseOverDatasets:
    def test_summary_stats(self, populated_store):
        s = j4.summarise_over_datasets(populated_store, "xgb", "auc")
        # xgb auc train=0.75, test=0.75 → mean=0.75
        assert s["n"] == 2
        assert pytest.approx(s["mean"], abs=1e-9) == 0.75
        assert pytest.approx(s["min"], abs=1e-9) == 0.75
        assert pytest.approx(s["max"], abs=1e-9) == 0.75

    def test_empty(self, store):
        s = j4.summarise_over_datasets(store, "nope", "auc")
        assert s["n"] == 0.0
        assert math.isnan(s["mean"])


class TestSliceByFeature:
    def test_aggregates_per_slice(self, populated_store):
        slices = j4.slice_by_feature(
            populated_store, model_id="xgb", dataset_id="train",
        )
        assert "gender=M" in slices
        assert "gender=F" in slices
        # xgb M auc=0.73
        assert pytest.approx(slices["gender=M"]["auc"], abs=1e-9) == 0.73

    def test_filter_slice_name(self, populated_store):
        slices = j4.slice_by_feature(
            populated_store, model_id="xgb", dataset_id="train",
            slice_name="gender=M",
        )
        assert "gender=M" in slices
        assert "gender=F" not in slices

    def test_no_match_returns_empty(self, populated_store):
        slices = j4.slice_by_feature(
            populated_store, model_id="rf", dataset_id="train",
            slice_name="age=young",
        )
        assert slices == {}


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = j4.J4_MODEL_EVAL_STORE_TOOL_NAMES
        assert "j4_record_evaluation" in names
        assert "j4_query_evaluations" in names
        assert "j4_compare_models" in names
        assert "j4_summarise_over_datasets" in names
        assert "j4_slice_by_feature" in names
