from __future__ import annotations

"""
ab_testing
==========

Deterministic statistical tools for A/B (and A/B/n) experiment analysis.

Implements the A1 — AB Testing Agent capability set from the
``docs/AGENT_SPEC_CATALOG.md`` plan:

* Sample Ratio Mismatch (SRM) detection
* Continuous / proportion metric analysis with auto test selection
* Multiple-comparison correction (Bonferroni, Benjamini-Hochberg)
* CUPED variance reduction (when a pre-experiment covariate is supplied)
* Sequential testing peeking warning (always-valid p-value guard)
* Decision recommendation (ship / iterate / abort) with reasoning

The tools here are pure-Python and depend only on ``numpy``, ``scipy`` and
``pandas`` so they can be unit-tested in isolation and reused outside the
LangGraph agent (e.g. inside the workflow runtime engine or batch scoring).
"""

import math  # noqa: E402, F401
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401
from scipy import stats  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float_array(values: Iterable[Any]) -> np.ndarray:
    """Convert an iterable of values to a 1-D float ndarray, dropping NaNs."""
    arr = np.asarray(list(values), dtype=float)
    return arr[~np.isnan(arr)]


def _cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Cohen's d for two independent samples (pooled std)."""
    if len(x) < 2 or len(y) < 2:
        return float("nan")
    nx, ny = len(x), len(y)
    var_x = float(np.var(x, ddof=1))
    var_y = float(np.var(y, ddof=1))
    pooled = math.sqrt(((nx - 1) * var_x + (ny - 1) * var_y) / (nx + ny - 2))
    if pooled == 0:
        return 0.0
    return float((np.mean(y) - np.mean(x)) / pooled)


def _wilson_ci(successes: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion."""
    if n == 0:
        return float("nan"), float("nan")
    z = stats.norm.ppf(1 - alpha / 2)
    p_hat = successes / n
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _mean_diff_ci(
    x: np.ndarray, y: np.ndarray, alpha: float = 0.05
) -> Tuple[float, float, float, float]:
    """Welch two-sample CI for the difference in means (y - x)."""
    nx, ny = len(x), len(y)
    mean_x = float(np.mean(x))
    mean_y = float(np.mean(y))
    var_x = float(np.var(x, ddof=1))
    var_y = float(np.var(y, ddof=1))
    se = math.sqrt(var_x / nx + var_y / ny)
    if se == 0:
        diff = mean_y - mean_x
        return diff, diff, diff, diff
    tcrit = stats.t.ppf(1 - alpha / 2, df=nx + ny - 2)
    diff = mean_y - mean_x
    return mean_x, mean_y, diff - tcrit * se, diff + tcrit * se


def _is_normal_enough(values: np.ndarray, alpha: float = 0.05) -> bool:
    """Shapiro–Wilk if n<=5000 else D'Agostino–Pearson; conservative fallback."""
    n = len(values)
    if n < 8:
        return True
    try:
        if n <= 5000:
            _, p = stats.shapiro(values)
        else:
            _, p = stats.normaltest(values)
        return p > alpha
    except Exception:
        return True


# ---------------------------------------------------------------------------
# 1. Sample Ratio Mismatch (SRM)
# ---------------------------------------------------------------------------


def check_sample_ratio_mismatch(
    data: pd.DataFrame,
    group_column: str,
    expected_split: Optional[Dict[str, float]] = None,
    alpha: float = 0.001,
) -> Dict[str, Any]:
    """
    Detect Sample Ratio Mismatch (SRM).

    Parameters
    ----------
    data : pd.DataFrame
        Experiment dataset with one row per user/observation.
    group_column : str
        Column identifying the variant (e.g. 'control', 'treatment_a').
    expected_split : dict, optional
        Expected proportions per variant. If ``None``, equal split is assumed.
    alpha : float, default 0.001
        Significance threshold. SRM checks typically use 0.001 to reduce
        false positives.

    Returns
    -------
    dict with:
        n_per_group, expected_per_group, observed_proportions,
        expected_proportions, chi2, p_value, srm_detected, warning.
    """
    if group_column not in data.columns:
        raise ValueError(f"group_column '{group_column}' not in data")

    counts = data[group_column].value_counts().to_dict()
    variants = sorted(counts.keys())
    observed = np.array([counts[v] for v in variants], dtype=float)
    total = float(observed.sum())

    if expected_split is None:
        expected = np.full(len(variants), 1.0 / len(variants))
    else:
        try:
            expected = np.array([float(expected_split[v]) for v in variants], dtype=float)
        except KeyError as exc:
            raise ValueError(
                f"expected_split missing variant '{exc.args[0]}' present in data"
            ) from exc
        expected = expected / expected.sum()

    expected_counts = expected * total
    # Guard against zero expected cell to avoid divide-by-zero.
    safe_expected = np.where(expected_counts == 0, 1e-9, expected_counts)
    chi2 = float(np.sum((observed - expected_counts) ** 2 / safe_expected))
    df = max(len(variants) - 1, 1)
    p_value = float(1 - stats.chi2.cdf(chi2, df=df))

    srm_detected = bool(p_value < alpha)
    warning = (
        f"SRM detected: observed counts {dict(zip(variants, observed.tolist()))} "
        f"deviate from expected proportions "
        f"{dict(zip(variants, (expected * 100).round(2).tolist()))}% "
        f"(chi2={chi2:.3f}, p={p_value:.4f}). Investigate before reading results."
        if srm_detected
        else "no SRM detected"
    )

    return {
        "n_per_group": dict(zip(variants, observed.astype(int).tolist())),
        "expected_per_group": dict(zip(variants, expected_counts.round(1).tolist())),
        "observed_proportions": dict(zip(variants, (observed / total).round(4).tolist())),
        "expected_proportions": dict(zip(variants, expected.round(4).tolist())),
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 6),
        "srm_detected": srm_detected,
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# 2. Continuous metric analysis
# ---------------------------------------------------------------------------


def analyze_continuous_metric(
    data: pd.DataFrame,
    group_column: str,
    metric_column: str,
    control_name: str = "control",
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Analyse a continuous metric between control and treatment group.

    Auto-selects Welch's t-test when both groups pass a normality check;
    otherwise falls back to Mann–Whitney U (non-parametric).

    Returns
    -------
    dict with control_n, treatment_n, control_mean, treatment_mean,
    absolute_lift, relative_lift, ci_low, ci_high, p_value, test_used,
    effect_size (Cohen's d).
    """
    for col in (group_column, metric_column):
        if col not in data.columns:
            raise ValueError(f"'{col}' missing from data")

    control = _to_float_array(data.loc[data[group_column] == control_name, metric_column])
    treatment = _to_float_array(data.loc[data[group_column] != control_name, metric_column])

    if len(control) < 2 or len(treatment) < 2:
        raise ValueError("Each variant must have at least 2 observations for a variance estimate")

    mean_x, mean_y, ci_low, ci_high = _mean_diff_ci(control, treatment, alpha=alpha)
    diff = mean_y - mean_x
    relative_lift = (diff / mean_x) if mean_x not in (0, 0.0) else float("nan")

    if _is_normal_enough(control) and _is_normal_enough(treatment):
        t_stat, p_value = stats.ttest_ind(treatment, control, equal_var=False)
        test_used = "welch_t"
    else:
        u_stat, p_value = stats.mannwhitneyu(treatment, control, alternative="two-sided")
        test_used = "mann_whitney_u"

    return {
        "metric": metric_column,
        "metric_type": "continuous",
        "test_used": test_used,
        "control_n": int(len(control)),
        "treatment_n": int(len(treatment)),
        "control_mean": round(mean_x, 6),
        "treatment_mean": round(mean_y, 6),
        "absolute_lift": round(diff, 6),
        "relative_lift": round(relative_lift, 6) if not math.isnan(relative_lift) else None,
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "p_value": float(round(float(p_value), 6)),
        "effect_size": round(_cohens_d(control, treatment), 4),
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# 3. Proportion metric analysis
# ---------------------------------------------------------------------------


def analyze_proportion_metric(
    data: pd.DataFrame,
    group_column: str,
    metric_column: str,
    control_name: str = "control",
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Analyse a binary (0/1) metric using a two-proportion z-test.

    Parameters
    ----------
    metric_column : str
        Column containing 0/1 values (any non-zero/non-one is treated as 1
        when truthy, 0 otherwise).

    Returns
    -------
    dict mirroring ``analyze_continuous_metric`` plus Wilson CIs.
    """
    for col in (group_column, metric_column):
        if col not in data.columns:
            raise ValueError(f"'{col}' missing from data")

    def successes(group_df: pd.DataFrame) -> Tuple[int, int]:
        values = (group_df[metric_column].astype(float) > 0).astype(int).to_numpy()
        return int(values.sum()), int(len(values))

    ctrl_df = data.loc[data[group_column] == control_name]
    treat_df = data.loc[data[group_column] != control_name]
    sc, nc = successes(ctrl_df)
    st, nt = successes(treat_df)

    if nc == 0 or nt == 0:
        raise ValueError("Each variant must have at least one observation")

    p_c = sc / nc
    p_t = st / nt
    pooled = (sc + st) / (nc + nt)
    se = math.sqrt(pooled * (1 - pooled) * (1 / nc + 1 / nt))
    if se == 0:
        z_stat = 0.0
        p_value = 1.0
    else:
        z_stat = (p_t - p_c) / se
        p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))

    ci_c = _wilson_ci(sc, nc, alpha=alpha)
    ci_t = _wilson_ci(st, nt, alpha=alpha)

    diff = p_t - p_c
    relative_lift = (diff / p_c) if p_c > 0 else float("nan")
    # Newcombe-style diff CI via simple normal approximation for brevity.
    se_diff = math.sqrt(p_c * (1 - p_c) / nc + p_t * (1 - p_t) / nt)
    zcrit = stats.norm.ppf(1 - alpha / 2)
    ci_low = diff - zcrit * se_diff
    ci_high = diff + zcrit * se_diff

    return {
        "metric": metric_column,
        "metric_type": "proportion",
        "test_used": "two_proportion_z",
        "control_n": nc,
        "treatment_n": nt,
        "control_successes": sc,
        "treatment_successes": st,
        "control_mean": round(p_c, 6),
        "treatment_mean": round(p_t, 6),
        "absolute_lift": round(diff, 6),
        "relative_lift": round(relative_lift, 6) if not math.isnan(relative_lift) else None,
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "control_ci": [round(ci_c[0], 6), round(ci_c[1], 6)],
        "treatment_ci": [round(ci_t[0], 6), round(ci_t[1], 6)],
        "p_value": float(round(p_value, 6)),
        "z_stat": round(float(z_stat), 4),
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# 4. CUPED variance reduction
# ---------------------------------------------------------------------------


def apply_cuped(
    data: pd.DataFrame,
    group_column: str,
    metric_column: str,
    covariate_column: str,
    control_name: str = "control",
) -> Dict[str, Any]:
    """
    Apply CUPED variance reduction.

    Uses a pre-experiment covariate to compute theta = Cov(Y, X) / Var(X)
    and returns adjusted means/lifts for control and treatment.

    Returns
    -------
    dict with theta, control_mean_raw, treatment_mean_raw,
    control_mean_adjusted, treatment_mean_adjusted, variance_reduction_pct.
    """
    for col in (group_column, metric_column, covariate_column):
        if col not in data.columns:
            raise ValueError(f"'{col}' missing from data")

    df = data[[group_column, metric_column, covariate_column]].dropna()
    if df.empty:
        raise ValueError("No non-null rows for CUPED")

    x = df[covariate_column].astype(float).to_numpy()
    y = df[metric_column].astype(float).to_numpy()
    var_x = float(np.var(x, ddof=0))
    if var_x == 0:
        raise ValueError("Covariate has zero variance; CUPED undefined")

    theta = float(np.cov(y, x, ddof=0)[0, 1] / var_x)

    df = df.copy()
    df["_cuped"] = y - theta * (x - float(np.mean(x)))
    control = df.loc[df[group_column] == control_name, "_cuped"].to_numpy()
    treatment = df.loc[df[group_column] != control_name, "_cuped"].to_numpy()

    raw_control = df.loc[df[group_column] == control_name, metric_column].astype(float).to_numpy()
    raw_treatment = df.loc[df[group_column] != control_name, metric_column].astype(float).to_numpy()

    var_raw = float(np.var(np.concatenate([raw_control, raw_treatment]), ddof=1))
    var_adj = float(np.var(np.concatenate([control, treatment]), ddof=1))
    reduction_pct = (1 - var_adj / var_raw) * 100 if var_raw > 0 else 0.0

    return {
        "covariate": covariate_column,
        "theta": round(theta, 6),
        "control_mean_raw": round(float(np.mean(raw_control)), 6),
        "treatment_mean_raw": round(float(np.mean(raw_treatment)), 6),
        "control_mean_adjusted": round(float(np.mean(control)), 6),
        "treatment_mean_adjusted": round(float(np.mean(treatment)), 6),
        "absolute_lift_adjusted": round(float(np.mean(treatment) - np.mean(control)), 6),
        "variance_reduction_pct": round(float(reduction_pct), 2),
        "n": int(len(df)),
    }


# ---------------------------------------------------------------------------
# 5. Multiple comparison correction
# ---------------------------------------------------------------------------


def apply_multiple_comparison_correction(
    p_values: Sequence[float],
    method: str = "bh",
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Adjust a list of p-values for multiple comparisons.

    Methods
    -------
    - ``"bonferroni"``: p_adj = min(p * m, 1.0)
    - ``"bh"`` (Benjamini–Hochberg FDR): controls false discovery rate
    - ``"none"``: returns p-values unchanged
    """
    method = method.lower()
    p = np.asarray(list(p_values), dtype=float)
    m = len(p)
    if m == 0:
        return {"method": method, "adjusted": [], "alpha": alpha}

    if method == "bonferroni":
        adjusted = np.minimum(p * m, 1.0)
    elif method == "bh":
        order = np.argsort(p)
        ranked = p[order]
        adj = ranked * m / (np.arange(1, m + 1))
        # Enforce monotonicity from the largest rank downward.
        adj = np.minimum.accumulate(adj[::-1])[::-1]
        adjusted = np.clip(adj, 0.0, 1.0)
        # Restore original order.
        out = np.empty(m, dtype=float)
        out[order] = adjusted
        adjusted = out
    elif method == "none":
        adjusted = p.copy()
    else:
        raise ValueError(f"unknown correction method '{method}'")

    return {
        "method": method,
        "alpha": alpha,
        "adjusted": [round(float(v), 6) for v in adjusted],
        "rejected": [bool(v < alpha) for v in adjusted],
    }


# ---------------------------------------------------------------------------
# 6. Sequential testing / peeking warning
# ---------------------------------------------------------------------------


def detect_sequential_peeking(
    sequential_p_values: Sequence[float],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Detect naive repeated significance testing (peeking).

    Given a chronological series of p-values from interim analyses, compare
    the smallest one against a Bonferroni-corrected threshold of
    ``alpha / n`` (number of looks) — this is the conservative bound that
    controls family-wise Type-I error under repeated looks.

    Naive significance: ``min(p) < alpha`` → "we crossed alpha once".
    Bonferroni-robust:  ``min(p) < alpha / n`` → "still significant after
    repeated-looks correction".

    A peeking risk is flagged when the analyst is naively significant
    but NOT Bonferroni-robust. For a proper always-valid test use
    mSPRT / alpha-spending functions (not implemented here).

    Returns
    -------
    dict with n_looks, min_p_value, bonferroni_threshold, naive_significant,
    bonferroni_significant, peeking_warning.
    """
    seq = np.asarray(list(sequential_p_values), dtype=float)
    seq = seq[~np.isnan(seq)]
    n = int(len(seq))
    if n == 0:
        return {
            "n_looks": 0,
            "min_p_value": None,
            "bonferroni_threshold": round(alpha, 6),
            "naive_significant": False,
            "bonferroni_significant": False,
            "peeking_warning": "no sequential observations provided",
        }

    min_p = float(np.min(seq))
    threshold = alpha / n  # Bonferroni correction for n repeated looks.
    naive_significant = bool(min_p < alpha)
    bonferroni_significant = bool(min_p < threshold)

    if naive_significant and not bonferroni_significant:
        warning = (
            f"Peeking risk: across {n} interim looks, the smallest p-value "
            f"({min_p:.4f}) crossed naive alpha={alpha} but NOT the "
            f"Bonferroni-corrected threshold ({threshold:.4f}). "
            "Effective Type-I error is inflated — confirm with a proper "
            "sequential test (mSPRT / alpha-spending) before shipping."
        )
    elif bonferroni_significant:
        warning = (
            f"Min p-value ({min_p:.4f}) crosses the Bonferroni-corrected "
            f"threshold ({threshold:.4f}) — robust to {n} repeated looks."
        )
    else:
        warning = (
            f"No interim look crossed naive alpha={alpha} "
            f"(min p={min_p:.4f}, Bonferroni threshold={threshold:.4f})."
        )

    return {
        "n_looks": n,
        "min_p_value": round(min_p, 6),
        "bonferroni_threshold": round(threshold, 6),
        "naive_significant": naive_significant,
        "bonferroni_significant": bonferroni_significant,
        "peeking_warning": warning,
    }


# ---------------------------------------------------------------------------
# 7. Decision recommendation
# ---------------------------------------------------------------------------


def recommend_decision(
    metric_result: Dict[str, Any],
    min_detectable_lift: Optional[float] = None,
    power: Optional[float] = None,
    required_sample_ratio: float = 1.0,
) -> Dict[str, Any]:
    """
    Translate a single metric's statistical result into a recommendation.

    Decision matrix
    ---------------
    - ship   : p < alpha AND practical-significance lift >= MDE
    - iterate: p < alpha AND lift < MDE (likely real but too small to ship)
    - abort  : p >= alpha AND no evidence of uplift
    - watch  : insufficient sample or guarded metric

    Parameters
    ----------
    metric_result : dict
        Output of ``analyze_continuous_metric`` /
        ``analyze_proportion_metric``.
    min_detectable_lift : float, optional
        Minimum lift (relative, e.g. 0.02 = 2%) deemed practically meaningful.
    power : float, optional
        Achieved statistical power (0–1). Reported when provided.
    required_sample_ratio : float, default 1.0
        Observed/required sample size ratio; <1 → underpowered, escalates
        ``watch`` instead of ``abort``.

    Returns
    -------
    dict with decision, rationale, p_value, lift, mde_met, underpowered.
    """
    p = metric_result.get("p_value", 1.0)
    lift = metric_result.get("relative_lift")
    alpha = metric_result.get("alpha", 0.05)

    mde_met = None
    if min_detectable_lift is not None and lift is not None:
        mde_met = abs(lift) >= abs(min_detectable_lift)

    underpowered = required_sample_ratio < 1.0
    significant = p < alpha

    if underpowered:
        decision = "watch"
        rationale = (
            f"Underpowered (sample ratio={required_sample_ratio:.2f}); "
            "extend the experiment before drawing a conclusion."
        )
    elif significant and (mde_met is True or min_detectable_lift is None):
        direction = "increase" if (lift is not None and lift > 0) else "change"
        decision = "ship"
        lift_str = f"{lift:.2%}" if lift is not None else "n/a"
        mde_str = f"{min_detectable_lift:.2%}" if min_detectable_lift is not None else "n/a"
        rationale = (
            f"Significant at alpha={alpha} (p={p:.4f}) with lift "
            f"{lift_str} meeting MDE {mde_str} → "
            f"recommend {direction}."
        )
    elif significant and mde_met is False:
        decision = "iterate"
        lift_str = f"{lift:.2%}" if lift is not None else "n/a"
        mde_str = f"{min_detectable_lift:.2%}" if min_detectable_lift is not None else "n/a"
        rationale = (
            f"Significant at alpha={alpha} (p={p:.4f}) but lift {lift_str} "
            f"is below the practical-significance MDE of {mde_str}; "
            "iterate before shipping."
        )
    else:
        decision = "abort"
        rationale = (
            f"No statistically significant effect (p={p:.4f} >= alpha={alpha}); "
            "abort or run longer."
        )

    out = {
        "metric": metric_result.get("metric"),
        "decision": decision,
        "rationale": rationale,
        "p_value": p,
        "lift": lift,
        "alpha": alpha,
        "significant": significant,
        "mde_met": mde_met,
        "underpowered": underpowered,
    }
    if power is not None:
        out["power"] = power
    return out


__all__ = [
    "check_sample_ratio_mismatch",
    "analyze_continuous_metric",
    "analyze_proportion_metric",
    "apply_cuped",
    "apply_multiple_comparison_correction",
    "detect_sequential_peeking",
    "recommend_decision",
]
