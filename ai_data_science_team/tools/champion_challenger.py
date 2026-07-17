from __future__ import annotations

"""
f2_champion_challenger
======================

Deterministic statistical tools for **F2 — Champion–Challenger
comparison** (spec from ``docs/specs/F2-champion-challenger.md``).

Implements the model-vs-model comparison protocol that G2
auto-retraining uses to decide whether a challenger should replace
the current champion.

Public surface
--------------
* :func:`mcnemar_test` — McNemar test (binary classifiers, paired).
* :func:`wilcoxon_signed_rank` — Wilcoxon (regression / continuous
  residuals, paired).
* :func:`auc_with_delong_ci` — AUC + DeLong 95 % CI (Sun & Xu 2014).
* :func:`compare_models` — end-to-end: load y_true + two model
  prediction frames, run tests, return a structured comparison
  artifact and a per-rule decision.
  by the LangGraph agent binding.
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_1d_float(arr: Sequence[float] | np.ndarray) -> np.ndarray:
    """Coerce to 1-D float array; raise ``ValueError`` for null/NaN inputs."""
    out = np.asarray(arr, dtype=float)
    if out.ndim != 1:
        out = out.ravel()
    if np.any(np.isnan(out)):
        raise ValueError("input contains NaN")
    return out


def _binary_labels(arr: Sequence[Any] | np.ndarray) -> np.ndarray:
    """Coerce to binary 0/1 int array; raise if non-binary."""
    out = np.asarray(arr)
    if out.dtype.kind not in "fiub":
        # Try to coerce through pandas
        out = pd.Series(out).astype(float).to_numpy()
    uniq = np.unique(out)
    if set(uniq.tolist()) <= {0.0, 1.0} or set(uniq.tolist()) <= {0, 1}:
        return out.astype(int)
    # Otherwise, treat anything >= 0.5 as positive
    return (out.astype(float) >= 0.5).astype(int)


# ---------------------------------------------------------------------------
# McNemar
# ---------------------------------------------------------------------------


def mcnemar_test(
    y_true: Sequence[Any],
    y_pred_a: Sequence[Any],
    y_pred_b: Sequence[Any],
    exact: bool = False,
    correction: bool = True,
) -> Dict[str, Any]:
    """McNemar test for paired binary classifiers.

    Parameters
    ----------
    y_true, y_pred_a, y_pred_b : array-like of binary labels.
    exact : bool
        If True, use the binomial exact test (slower).
    correction : bool
        Continuity correction (default True).

    Returns
    -------
    dict with keys ``statistic``, ``p_value``, ``b``, ``c``,
    ``n_disagreeing``, ``direction``.
    """
    y_true = _binary_labels(y_true)
    a = _binary_labels(y_pred_a)
    b = _binary_labels(y_pred_b)
    if y_true.shape != a.shape or y_true.shape != b.shape:
        raise ValueError("y_true, y_pred_a, y_pred_b must have the same length")

    correct_a = a == y_true
    correct_b = b == y_true
    b_count = int(((~correct_a) & correct_b).sum())  # A wrong, B right
    c_count = int((correct_a & (~correct_b)).sum())  # A right, B wrong

    n = b_count + c_count
    if n == 0:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "b": b_count,
            "c": c_count,
            "n_disagreeing": 0,
            "direction": "tie",
        }
    if exact:
        from math import comb  # noqa: E402, F401

        k = min(b_count, c_count)
        p = 0.0
        for j in range(k + 1):
            p += comb(n, j) * (0.5 ** n)
        p_value = min(1.0, 2 * p)
        statistic = float(min(b_count, c_count))
    else:
        chi2 = (abs(b_count - c_count) - (1 if correction else 0)) ** 2 / n
        # 1-dof chi-square survival
        try:
            from scipy.stats import chi2 as chi2_dist  # noqa: E402, F401

            p_value = float(chi2_dist.sf(chi2, df=1))
        except ImportError:
            # Fallback: 1 - erf(sqrt(chi2/2))
            from math import erf, sqrt  # noqa: E402, F401

            p_value = 1.0 - erf(sqrt(chi2 / 2))
        statistic = float(chi2)

    if b_count > c_count:
        direction = "b_better"  # A wrong, B right
    elif c_count > b_count:
        direction = "a_better"
    else:
        direction = "tie"

    return {
        "statistic": statistic,
        "p_value": p_value,
        "b": b_count,
        "c": c_count,
        "n_disagreeing": n,
        "direction": direction,
    }


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank (regression residuals)
# ---------------------------------------------------------------------------


def wilcoxon_signed_rank(
    residuals_a: Sequence[float],
    residuals_b: Sequence[float],
    alternative: str = "two-sided",
) -> Dict[str, Any]:
    """Paired Wilcoxon signed-rank test on residual pairs.

    Parameters
    ----------
    residuals_a, residuals_b : array-like
        Paired residual series.  We test for a systematic difference
        ``residuals_a - residuals_b`` (positive ⇒ A has larger residuals).
    alternative : {"two-sided", "less", "greater"}

    Returns
    -------
    dict with keys ``statistic``, ``p_value``, ``mean_diff``, ``n``.
    """
    a = _as_1d_float(residuals_a)
    b = _as_1d_float(residuals_b)
    if a.shape != b.shape:
        raise ValueError("residual arrays must have the same length")
    diff = a - b
    mean_diff = float(np.mean(diff))
    n = int(a.shape[0])
    if n == 0 or np.allclose(diff, 0):
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "mean_diff": mean_diff,
            "n": n,
        }
    try:
        from scipy.stats import wilcoxon  # noqa: E402, F401

        res = wilcoxon(a, b, alternative=alternative, zero_method="wilcox")
        return {
            "statistic": float(res.statistic),
            "p_value": float(res.pvalue),
            "mean_diff": mean_diff,
            "n": n,
        }
    except ImportError:
        # Fallback: sign-rank statistic with normal approximation.
        ranks = np.argsort(np.argsort(np.abs(diff)) + 1)
        w_plus = float(np.sum(ranks[(diff > 0)]))
        w_minus = float(np.sum(ranks[(diff < 0)]))
        stat = min(w_plus, w_minus)
        n_nonzero = int(np.sum(diff != 0))
        from math import erf, sqrt  # noqa: E402, F401

        z = (w_plus - n_nonzero * (n_nonzero + 1) / 4.0) / sqrt(
            n_nonzero * (n_nonzero + 1) * (2 * n_nonzero + 1) / 24.0
        )
        if alternative == "two-sided":
            p = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
        elif alternative == "less":
            p = 0.5 * (1 + erf(z / sqrt(2)))
        else:
            p = 0.5 * (1 - erf(z / sqrt(2)))
        return {
            "statistic": float(stat),
            "p_value": float(min(1.0, p)),
            "mean_diff": mean_diff,
            "n": n,
        }


# ---------------------------------------------------------------------------
# DeLong AUC variance (Sun & Xu 2014 fast algorithm)
# ---------------------------------------------------------------------------


def _placement_values(y_true_int: np.ndarray, scores: np.ndarray) -> np.ndarray:
    """Compute DeLong placement values V_i = P(X > X_i | Y=1).
    X is scores, Y is binary outcome.
    """
    pos_scores = scores[y_true_int == 1]
    neg_scores = scores[y_true_int == 0]
    if pos_scores.size == 0 or neg_scores.size == 0:
        return np.zeros_like(pos_scores, dtype=float)
    # V_i for each positive sample: count negatives with strictly smaller
    # score plus half for ties.
    counts = np.zeros(pos_scores.shape[0], dtype=float)
    for i, s in enumerate(pos_scores):
        less = (neg_scores < s).sum()
        tied = (neg_scores == s).sum()
        counts[i] = less + 0.5 * tied
    return counts / neg_scores.shape[0]


def _auc(y_true_int: np.ndarray, scores: np.ndarray) -> float:
    """Compute Mann–Whitney AUC."""
    pos = scores[y_true_int == 1]
    neg = scores[y_true_int == 0]
    if pos.size == 0 or neg.size == 0:
        return 0.5
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def auc_with_delong_ci(
    y_true: Sequence[Any],
    scores: Sequence[float],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """AUC with DeLong 95% confidence interval.

    Implementation follows Sun & Xu (2014) "Fast Implementation of
    DeLong's Algorithm for AUC" — placement values + structural
    variance.

    Returns
    -------
    dict with keys ``auc``, ``ci_low``, ``ci_high``, ``variance``.
    """
    y_true_int = _binary_labels(y_true)
    scores = _as_1d_float(scores)
    if y_true_int.shape[0] != scores.shape[0]:
        raise ValueError("y_true and scores must have the same length")

    m = int((y_true_int == 1).sum())  # positives
    n = int((y_true_int == 0).sum())  # negatives
    if m == 0 or n == 0:
        return {"auc": 0.5, "ci_low": 0.5, "ci_high": 0.5, "variance": 0.0}

    auc_val = _auc(y_true_int, scores)
    v10 = _placement_values(y_true_int, scores)  # shape (m,)
    # Placement values for negatives: structural symmetric implementation
    neg_scores = scores[y_true_int == 0]
    pos_scores = scores[y_true_int == 1]
    v01 = np.zeros(n, dtype=float)
    for j, s in enumerate(neg_scores):
        greater = (pos_scores > s).sum()
        tied = (pos_scores == s).sum()
        v01[j] = (greater + 0.5 * tied) / m

    # Variance-covariance matrix (10x10) approximated by sample covariance.
    s10 = np.var(v10, ddof=1) if m > 1 else 0.0
    s01 = np.var(v01, ddof=1) if n > 1 else 0.0
    var_auc = s10 / m + s01 / n

    # Standard normal quantiles for CI.
    try:
        from scipy.stats import norm  # noqa: E402, F401

        z = float(norm.ppf(1 - alpha / 2))
    except ImportError:
        # 1.96 fallback
        z = 1.959963984540054 if alpha == 0.05 else 1.6448536269514722

    ci_low = float(max(0.0, auc_val - z * np.sqrt(var_auc)))
    ci_high = float(min(1.0, auc_val + z * np.sqrt(var_auc)))
    return {
        "auc": float(auc_val),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "variance": float(var_auc),
    }


def delong_pvalue(
    y_true: Sequence[Any],
    scores_a: Sequence[float],
    scores_b: Sequence[float],
) -> Dict[str, Any]:
    """Two-sided DeLong test comparing AUCs of two classifiers.

    Returns
    -------
    dict with keys ``auc_a``, ``auc_b``, ``auc_diff``, ``ci95``,
    ``p_value``, ``statistic``.
    """
    a_res = auc_with_delong_ci(y_true, scores_a)
    b_res = auc_with_delong_ci(y_true, scores_b)
    auc_diff = b_res["auc"] - a_res["auc"]

    # Combined variance via pooled placement values (Sun & Xu 2014 §3).
    y_int = _binary_labels(y_true)
    sa = _as_1d_float(scores_a)
    sb = _as_1d_float(scores_b)
    m = int((y_int == 1).sum())
    n = int((y_int == 0).sum())
    if m == 0 or n == 0:
        return {
            "auc_a": a_res["auc"],
            "auc_b": b_res["auc"],
            "auc_diff": float(auc_diff),
            "ci95": [0.0, 0.0],
            "p_value": 1.0,
            "statistic": 0.0,
        }
    v10_a = _placement_values(y_int, sa)
    v10_b = _placement_values(y_int, sb)
    s10 = np.cov(
        np.stack([v10_a, v10_b], axis=0), ddof=1
    )
    # S10 is 2x2; we want S10[0,0]/m + S10[1,1]/m - 2*S10[0,1]/m
    var = float(s10[0, 0] / m + s10[1, 1] / m - 2 * s10[0, 1] / m)
    if var <= 0:
        var = 1e-12

    z = float(auc_diff) / float(np.sqrt(var))
    try:
        from scipy.stats import norm  # noqa: E402, F401

        p_value = float(2 * (1 - norm.cdf(abs(z))))
    except ImportError:
        from math import erf, sqrt  # noqa: E402, F401

        p_value = float((1 - erf(abs(z) / sqrt(2))))
    return {
        "auc_a": a_res["auc"],
        "auc_b": b_res["auc"],
        "auc_diff": float(auc_diff),
        "ci95": [
            float(auc_diff - 1.959963984540054 * np.sqrt(var)),
            float(auc_diff + 1.959963984540054 * np.sqrt(var)),
        ],
        "p_value": min(1.0, p_value),
        "statistic": float(z),
    }


# ---------------------------------------------------------------------------
# End-to-end comparison
# ---------------------------------------------------------------------------


def compare_models(
    y_true: Sequence[Any],
    y_proba_a: Sequence[float],
    y_proba_b: Sequence[float],
    *,
    primary_metric: str = "auc",
    alpha: float = 0.05,
    min_effect: float = 0.005,
    segment_columns: Optional[Sequence[Any]] = None,
    y_pred_a: Optional[Sequence[Any]] = None,
    y_pred_b: Optional[Sequence[Any]] = None,
    regression_residuals_a: Optional[Sequence[float]] = None,
    regression_residuals_b: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """End-to-end champion vs challenger comparison.

    Parameters
    ----------
    y_true : array-like, binary
    y_proba_a, y_proba_b : array-like of scores (floats in 0..1 or any
        ranking; passed both to ``auc_with_delong_ci``).
    primary_metric : str
        ``"auc"`` (default) or ``"wilcoxon"`` — switches the test panel.
    alpha : float
    min_effect : float
        Minimum AUC difference required to call ``"promote"``.
    segment_columns : sequence, optional
        Iterable of arrays aligned with ``y_true``; if supplied, AUC
        difference is recomputed within each segment.
    y_pred_a, y_pred_b : array-like of binary 0/1
        Required for ``mcnemar`` (only used when both are supplied).
    regression_residuals_a, regression_residuals_b : array-like
        Required for ``wilcoxon`` mode (regression comparison).

    Returns
    -------
    dict with keys ``metrics.champion``/``challenger`` (each with
    ``auc`` if computable), ``tests`` (mcnemar, delong, wilcoxon
    keyed by availability), ``segments`` (list of per-segment AUC
    diffs), ``recommendation``, ``rationale``, ``warnings``.
    """
    warnings: List[str] = []
    n = len(y_true)
    if n < 30:
        raise ValueError("y_true has fewer than 30 rows — comparison not reliable")
    if n < 200:
        warnings.append(f"low power: n={n} < 200")

    auc_a = auc_with_delong_ci(y_true, y_proba_a)
    auc_b = auc_with_delong_ci(y_true, y_proba_b)
    metrics = {
        "champion": {"auc": auc_a["auc"]},
        "challenger": {"auc": auc_b["auc"]},
    }
    metrics["champion"]["auc_ci95"] = [auc_a["ci_low"], auc_a["ci_high"]]
    metrics["challenger"]["auc_ci95"] = [auc_b["ci_low"], auc_b["ci_high"]]

    tests: Dict[str, Any] = {}

    # DeLong on the full sample
    delong = delong_pvalue(y_true, y_proba_a, y_proba_b)
    tests["delong"] = {
        "auc_diff": delong["auc_diff"],
        "ci95": delong["ci95"],
        "p_value": delong["p_value"],
        "statistic": delong["statistic"],
    }

    # McNemar when binary predictions are available
    if y_pred_a is not None and y_pred_b is not None:
        mcn = mcnemar_test(y_true, y_pred_a, y_pred_b)
        tests["mcnemar"] = {
            "statistic": mcn["statistic"],
            "p_value": mcn["p_value"],
            "b": mcn["b"],
            "c": mcn["c"],
            "direction": mcn["direction"],
        }

    # Wilcoxon when residuals are provided
    if (
        regression_residuals_a is not None
        and regression_residuals_b is not None
    ):
        wil = wilcoxon_signed_rank(regression_residuals_a, regression_residuals_b)
        tests["wilcoxon"] = wil

    # Segments
    segment_reports: List[Dict[str, Any]] = []
    if segment_columns:
        for label, seg_mask in _iter_segments(segment_columns, n):
            try:
                yt = np.asarray(y_true)[seg_mask]
                pa = np.asarray(y_proba_a)[seg_mask]
                pb = np.asarray(y_proba_b)[seg_mask]
                if len(yt) < 30:
                    continue
                seg_d = delong_pvalue(yt, pa, pb)
                segment_reports.append(
                    {
                        "segment": label,
                        "n": int(seg_mask.sum()),
                        "auc_diff": seg_d["auc_diff"],
                        "p_value": seg_d["p_value"],
                    }
                )
            except (ValueError, IndexError):
                continue

    # Decision rule
    test = tests.get("delong", {})
    auc_diff = float(test.get("auc_diff", 0.0))
    p_value = float(test.get("p_value", 1.0))
    if auc_diff >= min_effect and p_value < alpha:
        recommendation = "promote"
        rationale = (
            f"AUC +{auc_diff:.4f} (p={p_value:.4f}) "
            f"exceeds min_effect {min_effect} at alpha {alpha}."
        )
    elif auc_diff > 0 and p_value < alpha:
        recommendation = "wait"
        rationale = (
            f"Challenger positive ({auc_diff:.4f}) but below "
            f"min_effect {min_effect}."
        )
    else:
        recommendation = "reject"
        if auc_diff <= 0:
            rationale = (
                f"Challenger AUC {auc_diff:+.4f} does not improve on "
                f"champion (p={p_value:.4f})."
            )
        else:
            rationale = (
                f"Difference not significant (p={p_value:.4f}, "
                f"alpha={alpha})."
            )

    return {
        "metrics": metrics,
        "tests": tests,
        "segments": segment_reports,
        "recommendation": recommendation,
        "rationale": rationale,
        "warnings": warnings,
        "comparison_id": None,  # populated by the workflow layer
    }


def _iter_segments(
    segment_columns: Sequence[Any], n: int
) -> List[Tuple[str, np.ndarray]]:
    """Iterate segments as ``(label, boolean_index)`` pairs.

    For 1-D column → groups by unique value.
    For multi-D (tuple) column → Cartesian product of unique values.
    """
    cols = list(segment_columns)
    # If single-element, normalise to a list.
    if not isinstance(cols[0], (list, tuple, np.ndarray)) and len(cols) > 1:
        cols = [cols]
    # Convert to numpy arrays of shape (n,) each.
    arrs = []
    for c in cols:
        if isinstance(c, (list, tuple, np.ndarray)) and not isinstance(c, str):
            arrs.append(np.asarray(c))
        else:
            arrs.append(np.asarray([c]))  # degenerate; treated as constant
    if len(arrs) == 1:
        arr = arrs[0]
        if arr.shape == (n,):
            for v in np.unique(arr):
                mask = arr == v
                yield (str(v), mask)
    else:
        # Cartesian
        stack = np.stack(arrs, axis=1)
        # For reasonable cardinality; bail if too many combos.
        uniq, inv = np.unique(stack, axis=0, return_inverse=True)
        if uniq.shape[0] > 50:
            return
        for idx, val in enumerate(uniq):
            mask = inv == idx
            label = ",".join(f"{v}" for v in val.tolist())
            yield (label, mask)


__all__ = [
    "mcnemar_test",
    "wilcoxon_signed_rank",
    "auc_with_delong_ci",
    "delong_pvalue",
    "compare_models",
]


