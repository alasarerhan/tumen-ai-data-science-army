"""
a6_uplift
========

Deterministic uplift-modeling tools supporting **A6 — Uplift
Modeling** (spec ``docs/specs/A6-uplift-modeling.md``).

Provides a two-model T-Learner (control + treatment), segment
classification per the Yadlowsky/Bichsel-Hanzi-Rudin four-quadrant
schema, and a Qini-style cumulative-gain curve.

Public surface
--------------

* :func:`two_model_uplift` — train separate P(Y|X, control) and
  P(Y|X, treatment) models with sklearn-friendly interface.
* :func:`classify_segments` — four-quadrant population segmentation.
* :func:`qini_curve` — cumulative incremental gain as a function of
  population fraction.
* :func:`A6_UPLIFT_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


SEGMENTS: List[str] = ["persuadables", "sure_things", "lost_causes", "sleeping_dogs"]


def two_model_uplift(
    X: np.ndarray,
    treatment: np.ndarray,
    y: np.ndarray,
) -> Dict[str, Any]:
    """Fit two logistic regressions and return per-row uplift scores."""
    if X.ndim != 2:
        raise ValueError(f"X must be 2-D, got {X.ndim}-D")
    if not set(np.unique(treatment).tolist()) <= {0, 1}:
        raise ValueError("treatment must be binary 0/1")

    Xs = StandardScaler().fit_transform(X)

    p_c = LogisticRegression(max_iter=300).fit(Xs[treatment == 0], y[treatment == 0])
    p_t = LogisticRegression(max_iter=300).fit(Xs[treatment == 1], y[treatment == 1])

    p_c_pred = p_c.predict_proba(Xs)[:, 1]
    p_t_pred = p_t.predict_proba(Xs)[:, 1]

    return {
        "uplift_scores": (p_t_pred - p_c_pred),
        "p_control": p_c_pred,
        "p_treatment": p_t_pred,
        "intercepts": {"control": float(p_c.intercept_[0]), "treatment": float(p_t.intercept_[0])},
        "method": "t_learner",
        "segments": list(SEGMENTS),
    }


def classify_segments(
    p_control: np.ndarray,
    p_treatment: np.ndarray,
    *,
    threshold: float = 0.5,
) -> Dict[str, np.ndarray]:
    """Classify each row into one of the four uplift quadrants.

    A row is a "persuadable" if P_t > threshold and P_c <= threshold;
    a "sure thing" if both > threshold; a "lost cause" if neither
    exceeds threshold; a "sleeping dog" if P_t <= threshold and
    P_c > threshold (negative responders).
    """
    p_c = np.asarray(p_control, dtype=float)
    p_t = np.asarray(p_treatment, dtype=float)
    if p_c.shape != p_t.shape:
        raise ValueError("p_control and p_treatment must share shape")
    persuadables = (p_t > threshold) & (p_c <= threshold)
    sure_things = (p_t > threshold) & (p_c > threshold)
    sleeping_dogs = (p_t <= threshold) & (p_c > threshold)
    lost_causes = (p_t <= threshold) & (p_c <= threshold)
    return {
        "persuadables": persuadables,
        "sure_things": sure_things,
        "sleeping_dogs": sleeping_dogs,
        "lost_causes": lost_causes,
    }


def qini_curve(
    uplift_scores: np.ndarray,
    treatment: np.ndarray,
    y: np.ndarray,
    *,
    n_bins: int = 20,
) -> Dict[str, Any]:
    """Compute the Qini-curve cumulative incremental gain."""
    order = np.argsort(-uplift_scores)
    tr_sorted = treatment[order]
    y_sorted = y[order]
    n_t = tr_sorted.sum()
    n_c = tr_sorted.size - n_t
    if n_t == 0 or n_c == 0:
        return {
            "bins": list(range(n_bins)),
            "cum_uplift": [0.0] * n_bins,
            "qini_score": 0.0,
        }

    cum_y_t = np.cumsum(y_sorted * tr_sorted) / n_t
    cum_y_c = np.cumsum(y_sorted * (1 - tr_sorted)) / n_c
    cum_uplift_full = cum_y_t - cum_y_c

    # Pick ``n_bins`` samples over [0, 1].
    frac = (np.arange(1, len(cum_uplift_full) + 1) / len(cum_uplift_full))
    if n_bins >= len(frac):
        idx = np.arange(len(frac))
    else:
        idx = np.linspace(0, len(frac) - 1, n_bins).round().astype(int)
    return {
        "bins": frac[idx].tolist(),
        "cum_uplift": cum_uplift_full[idx].tolist(),
        "qini_score": float(cum_uplift_full[-1]),
    }


__all__ = [
    "SEGMENTS",
    "two_model_uplift",
    "classify_segments",
    "qini_curve",
    "A6_UPLIFT_TOOL_NAMES",
]


A6_UPLIFT_TOOL_NAMES = [
    "a6_two_model_uplift",
    "a6_classify_segments",
    "a6_qini_curve",
]
