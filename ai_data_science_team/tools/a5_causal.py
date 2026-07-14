"""
a5_causal
=========

Deterministic observational-causal tools supporting **A5 — Causal
Inference** (spec ``docs/specs/A5-causal-inference.md``).

Provides DiD-style lift, naive adjustment, propensity-overlap sanity
checks.  Both reflect the spec contract: simple, defensible core
that the agent can rely on while leaving the high-fidelity IV /
DiD-for-continuous methods to dedicated frameworks.

Public surface
--------------

* :func:`did_lift` — diff-in-diff estimator on a treatment panel.
* :func:`adj_lift` — adjusted mean difference after demeaning.
* :func:`check_propensity_overlap` — sanity check on cov-support.
* :func:`e_value` — E-value sensitivity bound.
* :func:`A5_CAUSAL_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np


def did_lift(
    pre_treat_y_pre: Sequence[float],
    pre_treat_y_post: Sequence[float],
    control_y_pre: Sequence[float],
    control_y_post: Sequence[float],
) -> Dict[str, Any]:
    """Diff-in-diff average treatment effect on the treated."""
    y_t_pre = float(np.mean(pre_treat_y_pre))
    y_t_post = float(np.mean(pre_treat_y_post))
    y_c_pre = float(np.mean(control_y_pre))
    y_c_post = float(np.mean(control_y_post))
    diff_t = y_t_post - y_t_pre
    diff_c = y_c_post - y_c_pre
    ate = diff_t - diff_c
    return {
        "ate": float(ate),
        "diff_treated": float(diff_t),
        "diff_control": float(diff_c),
        "n_treated": int(len(pre_treat_y_pre)),
        "n_control": int(len(control_y_pre)),
    }


def adj_lift(
    y: Sequence[float],
    treatment: Sequence[int],
    covariates: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    """Adjusted mean difference with one-hot treatment assignment.

    Returns ``ate``, ``n``, ``r2`` summary for the regression
    ``y ~ treatment + covariates``.
    """
    y_arr = np.asarray(list(y), dtype=float)
    t_arr = np.asarray(list(treatment), dtype=int)
    cov = np.asarray(list(covariates), dtype=float)
    # Accept either a 1-D sequence of length n (one covariate column)
    # or a 2-D shape (1, n) / (k, n) — columns must equal n.
    if cov.ndim == 1:
        cov = cov.reshape(-1, 1)
    elif cov.ndim == 2 and cov.shape[0] == y_arr.size and cov.shape[1] != y_arr.size:
        # shape (1, n) — single covariate passed as a row of columns.
        cov = cov.reshape(-1, cov.shape[1])
    if t_arr.size < 2 or cov.shape[0] != y_arr.size:
        raise ValueError(
            f"shape mismatch: y={y_arr.shape}, treatment={t_arr.shape}, "
            f"covariates={cov.shape}"
        )
    if set(t_arr.tolist()) - {0, 1}:
        raise ValueError("treatment must be binary 0/1")
    X = np.hstack([t_arr.reshape(-1, 1), cov])
    X_aug = np.hstack([np.ones((X.shape[0], 1)), X])
    beta, *_ = np.linalg.lstsq(X_aug, y_arr, rcond=None)
    ss_res = float(np.sum((y_arr - X_aug @ beta) ** 2))
    ss_tot = float(np.sum((y_arr - np.mean(y_arr)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        "ate": float(beta[1]),
        "intercept": float(beta[0]),
        "r2": float(r2),
        "n": int(y_arr.size),
        "n_covariates": int(cov.shape[1]),
    }


def check_propensity_overlap(
    propensity: Sequence[float], label: str = "treatment"
) -> Dict[str, Any]:
    """Sanity check on the propensity-score support.

    Common-support issues cause biased IPTW estimates.  Here we report
    q05/q25/q50/q75/q95 plus the share of mass under 0.05 / over
    0.95.  Heavy tails suggest covariates that drive extreme weights.
    """
    arr = np.asarray(propensity, dtype=float).ravel()
    if arr.size == 0:
        return {label: {}, "share_extreme_low": 0.0, "share_extreme_high": 0.0}
    quantiles = {
        "q05": float(np.percentile(arr, 5)),
        "q25": float(np.percentile(arr, 25)),
        "q50": float(np.percentile(arr, 50)),
        "q75": float(np.percentile(arr, 75)),
        "q95": float(np.percentile(arr, 95)),
    }
    share_low = float(np.mean(arr < 0.05))
    share_high = float(np.mean(arr > 0.95))
    return {
        label: quantiles,
        "share_extreme_low": share_low,
        "share_extreme_high": share_high,
        "overlap_ok": share_low < 0.10 and share_high < 0.10,
    }


def e_value(point_estimate: float, *, alpha: float = 0.05) -> float:
    """E-value sensitivity bound (Vansteelandt 2017).

    E-value = (OR(p)) + sqrt(OR(p) × (OR(p) - 1)) for p > 1 / 0
    returns the minimum strength an unmeasured confounder would need to
    fully explain the observed association.
    """
    p = abs(float(point_estimate))
    if p < 1:
        p = 1.0 / max(p, 1e-6)
    z = (p + np.sqrt(p * (p - 1.0))) if p > 1 else p
    return float(z)


__all__ = [
    "did_lift",
    "adj_lift",
    "check_propensity_overlap",
    "e_value",
    "A5_CAUSAL_TOOL_NAMES",
]


A5_CAUSAL_TOOL_NAMES = [
    "a5_did_lift",
    "a5_adj_lift",
    "a5_propensity_overlap",
    "a5_e_value",
]
