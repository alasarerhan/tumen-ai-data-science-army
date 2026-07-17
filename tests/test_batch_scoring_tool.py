"""
Tests for ``ai_data_science_team.tools.batch_scoring`` (G4 tool layer).
"""

from __future__ import annotations

import os
import warnings

# Apple Silicon segfault knob for xgboost/lightgbm, same as E1 tests.
os.environ.setdefault("OMP_NUM_THREADS", "1")

# Set env FIRST, then imports — they must observe the env.
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402

warnings.filterwarnings("ignore")

from ai_data_science_team.tools.batch_scoring import (  # noqa: E402
    align_features,
    chunked_predict,
    predict_dataframe,
    resolve_model,
    scoring_report,
)


@pytest.fixture
def trained_logreg() -> LogisticRegression:
    rng = np.random.RandomState(0)
    X = rng.normal(size=(200, 3))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
    clf = LogisticRegression(max_iter=200)
    clf.fit(X, y)
    return clf


class TestAlignFeatures:
    def test_alignment_pads_missing(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        aligned = align_features(df, ["a", "b", "c"], fill_value=-1)
        assert list(aligned.aligned.columns) == ["a", "b", "c"]
        assert aligned.missing == ["c"]
        assert aligned.extra == []

    def test_alignment_drops_extras(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4], "extra": [5, 6]})
        aligned = align_features(df, ["a", "b"])
        assert aligned.missing == []
        assert aligned.extra == ["extra"]
        assert "extra" not in aligned.aligned.columns

    def test_alignment_records_reorder(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        aligned = align_features(df, ["b", "a"])
        assert aligned.reordered is True
        assert list(aligned.aligned.columns) == ["b", "a"]


class TestResolveModel:
    def test_none_raises(self):
        with pytest.raises(ValueError):
            resolve_model(None)

    def test_invalid_object_raises(self):
        with pytest.raises(ValueError):
            resolve_model(object())


class TestPredictDataframe:
    def test_basic_predict(self, trained_logreg):
        df = pd.DataFrame(
            {
                "x0": [0.1, -0.5, 0.7],
                "x1": [0.2, 0.1, -0.3],
                "x2": [0.0, 0.0, 0.0],
            }
        )
        out, alignment = predict_dataframe(
            df,
            trained_logreg,
            feature_columns=["x0", "x1", "x2"],
            prediction_column="pred",
        )
        assert "pred" in out.columns
        assert alignment.missing == []
        assert alignment.extra == []
        assert set(out["pred"].tolist()) <= {0, 1}

    def test_includes_probabilities(self, trained_logreg):
        df = pd.DataFrame(
            {
                "x0": [0.1, -0.5],
                "x1": [0.2, 0.1],
                "x2": [0.0, 0.0],
            }
        )
        out, _ = predict_dataframe(
            df,
            trained_logreg,
            feature_columns=["x0", "x1", "x2"],
            prediction_column="pred",
            include_probabilities=True,
            proba_class_column="p1",
        )
        assert "p1" in out.columns
        assert ((out["p1"] >= 0) & (out["p1"] <= 1)).all()

    def test_missing_feature_columns_filled(self, trained_logreg):
        # Only x0 present in df; x1, x2 missing.
        df = pd.DataFrame({"x0": [0.1, 0.2, 0.3]})
        out, alignment = predict_dataframe(
            df,
            trained_logreg,
            feature_columns=["x0", "x1", "x2"],
            prediction_column="pred",
            fill_value=0.0,
        )
        assert "pred" in out.columns
        assert alignment.missing == ["x1", "x2"]
        assert len(out) == 3

    def test_auto_feature_columns_from_model(self):
        # Train a quick RandomForest so the fitted feature_names_in_
        # attribute is populated.
        rng = np.random.RandomState(0)
        X = rng.normal(size=(200, 3))
        y = (X[:, 0] + 0.5 * X[:, 1] > 0).astype(int)
        rf = RandomForestClassifier(n_estimators=20, random_state=0)
        rf.fit(X, y)

        df = pd.DataFrame(
            {
                "x0": [0.1, -0.5],
                "x1": [0.2, 0.1],
                "x2": [0.0, 0.0],
                "ignored_col": [1, 2],
            }
        )
        out, alignment = predict_dataframe(
            df, rf, feature_columns="auto", prediction_column="pred"
        )
        assert "pred" in out.columns
        assert alignment.missing == []
        assert "ignored_col" in alignment.extra


class TestChunkedPredict:
    def test_chunked_predict_runs(self, trained_logreg):
        rng = np.random.RandomState(0)
        df = pd.DataFrame(
            {
                "x0": rng.normal(size=120),
                "x1": rng.normal(size=120),
                "x2": rng.normal(size=120),
            }
        )
        merged, alignment, runtime = chunked_predict(
            df,
            trained_logreg,
            chunk_size=40,
            feature_columns=["x0", "x1", "x2"],
            prediction_column="pred",
        )
        assert len(merged) == 120
        assert runtime["rows_scored"] == 120
        assert runtime["n_chunks"] == 3
        assert runtime["duration_s"] >= 0.0
        assert alignment.missing == []

    def test_chunk_size_must_be_positive(self, trained_logreg):
        df = pd.DataFrame({"x0": [0.1]})
        with pytest.raises(ValueError):
            chunked_predict(df, trained_logreg, chunk_size=0)


class TestScoringReport:
    def test_basic(self):
        rep = scoring_report(100, 1.5, "models:/demo/3")
        d = rep.to_dict()
        assert d["rows_scored"] == 100
        assert d["duration_s"] == 1.5
        assert d["model_uri"] == "models:/demo/3"

    def test_extra_keys(self):
        rep = scoring_report(10, 0.5, "models:/x", n_chunks=2, chunk_size=5)
        d = rep.to_dict()
        assert d["n_chunks"] == 2
        assert d["chunk_size"] == 5
