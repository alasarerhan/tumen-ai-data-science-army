from __future__ import annotations

"""
g4_batch_scoring
================

Deterministic batch-prediction tools for **G4 — Batch Scoring +
``model.predict`` node** (spec ``docs/specs/G4-batch-scoring.md``).

Pipeline içinde kayıtlı bir modeli dataframe üzerinde çalıştırarak
tahmin kolonunu ekler; chunk'lı çalışır; şema uyuşmazlığını anlaşılır
hata ile raporlar. Mevcut ``ModelServingAgent.load_model/
run_inference`` ile uyumlu sözleşmeyi korur.

Public surface
--------------

* :func:`align_features` — reorder / select columns to match model's
  training-time feature ordering; surface missing / extra columns.
* :func:`predict_dataframe` — predict on a DataFrame; supports
  pipelines that expose ``predict`` and ``predict_proba``.
* :func:`chunked_predict` — same as :func:`predict_dataframe` but
  processes the frame in chunks of ``chunk_size``.
* :func:`scoring_report` — produce the ``scoring_report`` node
  output described in spec §2.
* :func:`resolve_model` — turn ``{model_id, version, stage,
  artifact}`` into a concrete model object.
"""

import time  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Schema alignment
# ---------------------------------------------------------------------------


@dataclass
class FeatureAlignment:
    """Result of aligning a DataFrame to a trained model's feature set."""

    aligned: pd.DataFrame
    missing: List[str]
    extra: List[str]
    reordered: bool


def align_features(
    df: pd.DataFrame,
    expected_features: Sequence[str],
    *,
    fill_value: Any = 0.0,
) -> FeatureAlignment:
    """Align ``df`` columns to ``expected_features``.

    - Missing columns are added with ``fill_value``.
    - Extra columns are dropped from the result.
    - The output is reordered to match the expected order.

    Returns
    -------
    FeatureAlignment with the aligned frame, plus lists of missing
    and extra columns (relative to the expected list) and a flag
    indicating whether reordering was necessary.
    """
    present = list(df.columns)
    missing = [f for f in expected_features if f not in present]
    extra = [f for f in present if f not in expected_features]

    aligned = df.copy()
    for f in missing:
        aligned[f] = fill_value
    aligned = aligned[list(expected_features)]
    return FeatureAlignment(
        aligned=aligned,
        missing=missing,
        extra=extra,
        reordered=aligned.columns.tolist() != present,
    )


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------


def resolve_model(model: Any) -> Any:
    """Pass through an already-loaded model.

    The model must implement either ``predict`` or ``predict_proba``.
    ``InferredModels`` (vocab from E1) expose both.  ``None`` and
    other sentinels raise ``ValueError``.
    """
    if model is None:
        raise ValueError("model must not be None")
    if not (hasattr(model, "predict") or hasattr(model, "predict_proba")):
        raise ValueError(
            "model must implement at least one of `predict` or "
            "`predict_proba`"
        )
    return model


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------


def predict_dataframe(
    df: pd.DataFrame,
    model: Any,
    *,
    feature_columns: Union[str, Sequence[str]] = "auto",
    prediction_column: str = "prediction",
    include_probabilities: bool = True,
    proba_class_column: Optional[str] = "prediction_proba",
    fill_value: Any = 0.0,
) -> Tuple[pd.DataFrame, FeatureAlignment]:
    """Score ``df`` with ``model``.

    Parameters
    ----------
    df : pd.DataFrame
        The input dataset.
    model : object
        Loaded model.  Must expose ``predict``; ``predict_proba`` is
        used when ``include_probabilities=True``.
    feature_columns :
        Either ``"auto"`` (use the model's ``feature_names_in_``
        attribute when available, else use every numeric column),
        or an explicit list of column names.
    prediction_column : str
        Name of the column that receives the deterministic
        ``predict`` output.
    include_probabilities : bool
        If True and the model supports ``predict_proba``, append
        the probability column.
    proba_class_column : str, optional
        Name used for the probability column when
        ``include_probabilities=True``.
    fill_value : Any
        Used for missing-feature columns when
        ``feature_columns != "auto"``.

    Returns
    -------
    (scored_df, alignment) — ``scored_df`` has the prediction (and
    optionally probability) column appended; ``alignment`` describes
    which columns were missing or extra.
    """
    model = resolve_model(model)
    if feature_columns == "auto":
        # Decide the expected feature list from the model when
        # available; otherwise fall back to every numeric column in
        # the input frame. ``feature_names_in_`` is set when a model
        # was fit on a pandas DataFrame; not every estimator has it.
        expected: Optional[List[str]] = None
        feature_names = getattr(model, "feature_names_in_", None)
        if feature_names is not None:
            try:
                expected = [str(name) for name in list(feature_names)]
            except TypeError:
                expected = None
        if expected is None:
            n_features = getattr(model, "n_features_in_", None)
            if isinstance(n_features, int) and len(df.columns) >= n_features:
                expected = list(df.columns[:n_features])
        if expected is None:
            expected = [
                c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])
            ]   
    elif isinstance(feature_columns, str):
        expected = [feature_columns]
    else:
        expected = list(feature_columns)

    alignment = align_features(df, expected, fill_value=fill_value)
    X = alignment.aligned.to_numpy()

    predictions = model.predict(X)
    out = df.copy()
    out[prediction_column] = np.asarray(predictions)

    if include_probabilities and hasattr(model, "predict_proba"):
        try:
            proba = model.predict_proba(X)
            if proba.ndim == 2 and proba.shape[1] >= 2:
                # Default to the positive-class probability.
                out[proba_class_column or "prediction_proba"] = proba[:, 1]
        except Exception:  # noqa: BLE001
            # Some models raise on predict_proba; skip silently.
            pass
    return out, alignment


# ---------------------------------------------------------------------------
# Chunked execution
# ---------------------------------------------------------------------------


def chunked_predict(
    df: pd.DataFrame,
    model: Any,
    *,
    chunk_size: int = 50_000,
    feature_columns: Union[str, Sequence[str]] = "auto",
    prediction_column: str = "prediction",
    include_probabilities: bool = True,
    proba_class_column: Optional[str] = "prediction_proba",
    fill_value: Any = 0.0,
) -> Tuple[pd.DataFrame, FeatureAlignment, Dict[str, Any]]:
    """Apply :func:`predict_dataframe` to ``df`` in chunks.

    Parameters are identical to ``predict_dataframe`` plus
    ``chunk_size`` (default 50 000 rows).  Returns the merged
    scored frame, the alignment summary (from the first chunk),
    and a runtime stats dict (rows scored, n_chunks, duration_s).
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    n = len(df)
    n_chunks = max(1, (n + chunk_size - 1) // chunk_size)
    chunks: List[pd.DataFrame] = []
    alignment: Optional[FeatureAlignment] = None

    start = time.monotonic()
    for start_idx in range(0, n, chunk_size):
        end_idx = min(start_idx + chunk_size, n)
        chunk = df.iloc[start_idx:end_idx]
        scored, align = predict_dataframe(
            chunk,
            model,
            feature_columns=feature_columns,
            prediction_column=prediction_column,
            include_probabilities=include_probabilities,
            proba_class_column=proba_class_column,
            fill_value=fill_value,
        )
        if alignment is None:
            alignment = align
        chunks.append(scored)
    duration = time.monotonic() - start
    merged = pd.concat(chunks, axis=0, ignore_index=True) if chunks else df.copy()
    runtime = {
        "rows_scored": int(n),
        "n_chunks": int(n_chunks),
        "duration_s": float(duration),
        "chunk_size": int(chunk_size),
    }
    assert alignment is not None  # populated because n > 0 implied
    return merged, alignment, runtime


# ---------------------------------------------------------------------------
# Scoring report (matches spec §2 node output)
# ---------------------------------------------------------------------------


@dataclass
class ScoringReport:
    rows_scored: int
    duration_s: float
    model_uri: str
    extra: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows_scored": self.rows_scored,
            "duration_s": self.duration_s,
            "model_uri": self.model_uri,
            **(self.extra or {}),
        }


def scoring_report(
    n_rows: int,
    duration_s: float,
    model_uri: str,
    **extra: Any,
) -> ScoringReport:
    """Wrap scoring stats into the spec's ``scoring_report`` shape."""
    return ScoringReport(
        rows_scored=int(n_rows),
        duration_s=float(duration_s),
        model_uri=str(model_uri),
        extra=dict(extra),
    )


__all__ = [
    "FeatureAlignment",
    "align_features",
    "resolve_model",
    "predict_dataframe",
    "chunked_predict",
    "scoring_report",
]


