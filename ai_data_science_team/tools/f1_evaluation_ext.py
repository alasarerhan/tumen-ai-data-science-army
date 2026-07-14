"""
f1_evaluation_ext
==================

Deterministic tools supporting **F1 — Evaluation Extension**
(spec ``docs/specs/F1-evaluation-ext.md``).

Adds three capabilities on top of the base evaluation agent:

* Calibration: Brier score, ECE, reliability curve.
* Threshold optimization: cost-matrix-driven threshold sweep.
* Segment evaluation: per-segment metrics breakdown.

Public surface
--------------

* :func:`evaluate_calibration` — Brier + ECE + reliability curve.
* :func:`optimize_threshold` — argmin threshold + expected cost.
* :func:`evaluate_segments` — per-segment metrics table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------


@dataclass
class CalibrationReport:
    brier_score: float
    ece: float
    reliability_curve: List[Dict[str, float]] = field(default_factory=list)
    n_samples: int = 0
    n_bins: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brier": self.brier_score,
            "ece": self.ece,
            "curve": list(self.reliability_curve),
            "n_samples": self.n_samples,
            "n_bins": self.n_bins,
        }


def _bucketize_for_ece(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int,
) -> List[Tuple[float, float, int]]:
    """Bucket predictions into ``n_bins`` equally-spaced bins."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out: List[Tuple[float, float, int]] = []
    for i in range(n_bins):
        lo, hi = float(edges[i]), float(edges[i + 1])
        if i == n_bins - 1:
            mask = (y_prob >= lo) & (y_prob <= hi)
        else:
            mask = (y_prob >= lo) & (y_prob < hi)
        if not mask.any():
            continue
        mean_pred = float(np.mean(y_prob[mask]))
        frac_pos = float(np.mean(y_true[mask]))
        out.append((mean_pred, frac_pos, int(mask.sum())))
    return out


def evaluate_calibration(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    n_bins: int = 10,
) -> CalibrationReport:
    """Compute calibration metrics for a binary classifier.

    Returns Brier score, Expected Calibration Error (ECE) and the
    reliability curve (mean-predicted-probability per bin).
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float).ravel()
    if y_true_arr.shape != y_prob_arr.shape:
        raise ValueError(
            f"shape mismatch: y_true {y_true_arr.shape} vs y_prob {y_prob_arr.shape}"
        )
    if y_true_arr.size == 0:
        return CalibrationReport(
            brier_score=0.0,
            ece=0.0,
            reliability_curve=[],
            n_samples=0,
            n_bins=n_bins,
        )

    brier = float(np.mean((y_prob_arr - y_true_arr) ** 2))

    buckets = _bucketize_for_ece(y_true_arr, y_prob_arr, int(n_bins))
    n = y_true_arr.size
    ece = 0.0
    curve: List[Dict[str, float]] = []
    for mean_pred, frac_pos, count in buckets:
        weight = count / n
        ece += abs(frac_pos - mean_pred) * weight
        curve.append(
            {
                "mean_pred": mean_pred,
                "frac_pos": frac_pos,
                "count": float(count),
            }
        )
    return CalibrationReport(
        brier_score=brier,
        ece=ece,
        reliability_curve=curve,
        n_samples=int(n),
        n_bins=int(n_bins),
    )


# ---------------------------------------------------------------------------
# Cost-based threshold optimization
# ---------------------------------------------------------------------------


@dataclass
class ThresholdReport:
    optimal_threshold: float
    expected_cost: float
    baseline_cost: float
    cost_curve: List[Dict[str, float]] = field(default_factory=list)
    cost_matrix: Dict[str, float] = field(default_factory=dict)
    n_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "optimal_threshold": self.optimal_threshold,
            "expected_cost": self.expected_cost,
            "baseline_cost": self.baseline_cost,
            "cost_curve": list(self.cost_curve),
            "cost_matrix": dict(self.cost_matrix),
            "n_samples": self.n_samples,
        }


def _cost_matrix(
    fp: float, fn: float, tp: float, tn: float
) -> Dict[str, float]:
    cm = {
        "fp": float(fp),
        "fn": float(fn),
        "tp": float(tp),
        "tn": float(tn),
    }
    return cm


def _expected_cost_at_threshold(
    y_true: np.ndarray, y_prob: np.ndarray, threshold: float, cm: Mapping[str, float]
) -> float:
    pred = (y_prob >= threshold).astype(int)
    # Confusion-matrix entries.
    tp = float(np.sum((pred == 1) & (y_true == 1)))
    fp = float(np.sum((pred == 1) & (y_true == 0)))
    fn = float(np.sum((pred == 0) & (y_true == 1)))
    tn = float(np.sum((pred == 0) & (y_true == 0)))
    return (
        tp * cm.get("tp", 0.0)
        + fp * cm.get("fp", 0.0)
        + fn * cm.get("fn", 0.0)
        + tn * cm.get("tn", 0.0)
    )


def optimize_threshold(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    *,
    fp: float = 1.0,
    fn: float = 1.0,
    tp: float = 0.0,
    tn: float = 0.0,
    step: float = 0.01,
) -> ThresholdReport:
    """Sweep thresholds from 0 to 1 by ``step`` and pick the argmin.

    A baseline cost (threshold=0.5 default) is also reported so the
    improvement over the user default is visible.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_prob, dtype=float).ravel()
    if y_true_arr.shape != y_prob_arr.shape:
        raise ValueError(
            f"shape mismatch: y_true {y_true_arr.shape} vs y_prob {y_prob_arr.shape}"
        )
    if y_true_arr.size == 0:
        return ThresholdReport(
            optimal_threshold=0.5,
            expected_cost=0.0,
            baseline_cost=0.0,
            cost_matrix=_cost_matrix(fp, fn, tp, tn),
            n_samples=0,
        )
    cm = _cost_matrix(fp, fn, tp, tn)

    best_t = 0.5
    best_cost = float("inf")
    curve: List[Dict[str, float]] = []
    t = 0.0
    while t <= 1.0 + 1e-9:
        cost = _expected_cost_at_threshold(
            y_true_arr, y_prob_arr, float(t), cm
        )
        curve.append({"threshold": float(round(t, 4)), "expected_cost": float(cost)})
        if cost < best_cost:
            best_cost = cost
            best_t = float(t)
        t += step
    baseline_cost = float(
        _expected_cost_at_threshold(y_true_arr, y_prob_arr, 0.5, cm)
    )
    return ThresholdReport(
        optimal_threshold=best_t,
        expected_cost=float(best_cost),
        baseline_cost=float(baseline_cost),
        cost_curve=curve,
        cost_matrix=cm,
        n_samples=int(y_true_arr.size),
    )


# ---------------------------------------------------------------------------
# Segment evaluation
# ---------------------------------------------------------------------------


@dataclass
class SegmentRow:
    segment: str
    n: int
    metric_name: str
    metric_value: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment": self.segment,
            "n": self.n,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
        }


def evaluate_segments(
    df: pd.DataFrame,
    y_true: Sequence[int],
    y_pred: Sequence[int],
    segment_columns: Sequence[str],
    *,
    metric: str = "accuracy",
) -> List[Dict[str, Any]]:
    """Per-segment metrics table.

    The default metric is ``accuracy``; ``metric`` accepts any callable
    taking ``(y_true, y_pred) -> float``.
    """
    if not segment_columns:
        raise ValueError("segment_columns must be non-empty")
    if df.shape[0] != len(list(y_true)):
        raise ValueError(
            f"df has {df.shape[0]} rows but y_true has {len(list(y_true))}"
        )
    if metric == "accuracy":
        from sklearn.metrics import accuracy_score

        score_fn = accuracy_score
    elif metric == "f1":
        from sklearn.metrics import f1_score

        score_fn = f1_score
    elif metric == "roc_auc":
        from sklearn.metrics import roc_auc_score

        # roc_auc requires probabilities — we operate on predictions here,
        # but we still implement the switch for completeness and to keep
        # the public surface coherent with the rest of the toolbox.
        score_fn = lambda yt, yp: float(roc_auc_score(yt, yp))
    else:
        raise ValueError(
            f"Unsupported metric '{metric}'. Use one of accuracy, f1, "
            "roc_auc or supply a callable."
        )

    yt_arr = np.asarray(y_true)
    yp_arr = np.asarray(y_pred)

    rows: List[Dict[str, Any]] = []
    if len(segment_columns) == 1:
        col = segment_columns[0]
        for value, group_df in df.groupby(col):
            idx = group_df.index.to_numpy()
            score = float(score_fn(yt_arr[idx], yp_arr[idx]))
            rows.append(
                SegmentRow(
                    segment=f"{col}={value}",
                    n=int(len(idx)),
                    metric_name=metric,
                    metric_value=score,
                ).to_dict()
            )
    else:
        # Multi-column Cartesian segmentation.
        grouped = df.groupby(list(segment_columns))
        for key, group_df in grouped:
            idx = group_df.index.to_numpy()
            score = float(score_fn(yt_arr[idx], yp_arr[idx]))
            seg_label = ",".join(
                f"{col}={v}" for col, v in zip(segment_columns, key)
            )
            rows.append(
                SegmentRow(
                    segment=seg_label,
                    n=int(len(idx)),
                    metric_name=metric,
                    metric_value=score,
                ).to_dict()
            )
    return rows


__all__ = [
    "CalibrationReport",
    "evaluate_calibration",
    "ThresholdReport",
    "optimize_threshold",
    "evaluate_segments",
]


