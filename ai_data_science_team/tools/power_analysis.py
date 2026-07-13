"""
power_analysis
==============

Deterministic statistical tools for **A2 — Power Analysis & Experiment
Design Agent** (spec from ``docs/AGENT_SPEC_CATALOG.md``).

Provides a unified power-analysis API wrapping
:mod:`statsmodels.stats.power` so the LLM-driven agent and the workflow
runtime can solve any one of the four classical power-analysis problems:

* a priori   — "How many observations do I need?"       (solve N)
* sensitivity — "What effect size can I detect?"        (solve MDE)
* post-hoc   — "Given the data, what was my power?"      (solve power)
* compromise  — "Given N and effect, find balanced α"   (solve alpha)

Plus auxiliary helpers:
* ``proportion_effect_size``  — Cohen's h for two rates
* ``estimate_runtime_days``   — days needed given daily traffic
* ``suggest_stratification``  — which columns to stratify by
* ``design_experiment``       — high-level façade returning a full design

The tools here are pure-Python; only ``numpy``, ``pandas`` and ``statsmodels``
are required so they can be reused outside the LangGraph runtime.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from statsmodels.stats.power import (
    NormalIndPower,
    TTestIndPower,
)
from statsmodels.stats.proportion import (
    proportion_confint,
    proportion_effectsize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for two proportions.

    :func:`statsmodels.stats.proportion.proportion_effectsize` returns a
    *signed* value (positive when p1 > p2). For sample-size / MDE /
    power calculations the magnitude is what matters, and z-scores from
    ``statsmodels.stats.power.NormalIndPower`` are always non-negative on
    the effect-size axis. We therefore take the absolute value to keep
    downstream numerics stable.
    """
    return abs(float(proportion_effectsize(p1, p2)))


def _cohens_d(mean_diff: float, pooled_sd: float) -> float:
    """Cohen's d effect size given raw mean difference and pooled SD."""
    if pooled_sd == 0:
        raise ValueError("pooled_sd must be non-zero for Cohen's d")
    return float(mean_diff / pooled_sd)


def _resolve_metric_type(
    metric_type: str,
    baseline_mean: Optional[float],
    baseline_sd: Optional[float],
    baseline_rate: Optional[float],
) -> str:
    """Resolve and validate the metric type from caller input."""
    metric_type = (metric_type or "auto").lower()
    if metric_type == "auto":
        if baseline_rate is not None:
            return "proportion"
        if baseline_mean is not None and baseline_sd is not None:
            return "continuous"
        raise ValueError(
            "Cannot auto-detect metric_type: supply baseline_rate or both "
            "baseline_mean and baseline_sd."
        )
    if metric_type not in {"continuous", "proportion"}:
        raise ValueError(
            f"metric_type must be 'continuous', 'proportion' or 'auto'; got {metric_type!r}"
        )
    return metric_type


# ---------------------------------------------------------------------------
# 1. Unified solve_power wrapper
# ---------------------------------------------------------------------------


def solve_power(
    solve_for: str,
    metric_type: str = "auto",
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    baseline_rate: Optional[float] = None,
    expected_lift: Optional[float] = None,
    expected_treatment_rate: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.8,
    nobs1: Optional[int] = None,
    ratio: float = 1.0,
    alternative: str = "two-sided",
) -> Dict[str, Any]:
    """
    Solve one parameter of the power equation.

    Parameters
    ----------
    solve_for : str
        One of ``"n"``, ``"power"``, ``"alpha"``, ``"effect_size"``.
    metric_type : str
        ``"continuous"`` (t-test) or ``"proportion"`` (z-test).
    baseline_mean, baseline_sd : float, optional
        Required for continuous metrics (mean and pooled SD of control).
    baseline_rate : float, optional
        Required for proportion metrics (control conversion rate, 0-1).
    expected_lift : float, optional
        Absolute mean lift (continuous) OR absolute rate lift (proportion).
    expected_treatment_rate : float, optional
        Alternative to ``expected_lift`` for proportion metrics.
    alpha, power, nobs1 : float
        Three of the four standard inputs.  The fourth is what
        ``solve_for`` requests.
    ratio : float, default 1.0
        Treatment-to-control sample size ratio.
    alternative : str, default "two-sided"
        ``"two-sided"``, ``"larger"`` or ``"smaller"``.

    Returns
    -------
    dict with the solved quantity, the inputs used, and the metric type.
    """
    metric_type = _resolve_metric_type(
        metric_type, baseline_mean, baseline_sd, baseline_rate
    )
    solve_for = solve_for.lower()
    if solve_for not in {"n", "power", "alpha", "effect_size"}:
        raise ValueError(
            "solve_for must be one of 'n', 'power', 'alpha', 'effect_size'"
        )

    # When we are solving for effect_size, the raw lift inputs are NOT needed.
    needs_raw_inputs = solve_for != "effect_size"
    engine = TTestIndPower() if metric_type == "continuous" else NormalIndPower()

    if metric_type == "continuous":
        if needs_raw_inputs and expected_lift is None:
            raise ValueError("expected_lift is required for continuous metrics")
        if needs_raw_inputs and (baseline_mean is None or baseline_sd is None):
            raise ValueError(
                "baseline_mean and baseline_sd are required for continuous metrics"
            )
        if needs_raw_inputs:
            effect_size: float = _cohens_d(expected_lift, baseline_sd)  # type: ignore[arg-type]
        else:
            effect_size = float("nan")  # sentinel — overridden by solver below
    else:
        if needs_raw_inputs:
            if expected_treatment_rate is not None:
                if not (0 < baseline_rate < 1):
                    raise ValueError("baseline_rate must be in (0, 1)")
                if not (0 < expected_treatment_rate < 1):
                    raise ValueError("expected_treatment_rate must be in (0, 1)")
                effect_size = _cohens_h(baseline_rate, expected_treatment_rate)
            elif expected_lift is not None:
                if not (0 < baseline_rate < 1):
                    raise ValueError("baseline_rate must be in (0, 1)")
                treatment_rate = baseline_rate + expected_lift
                if not (0 < treatment_rate < 1):
                    raise ValueError(
                        f"treatment_rate={treatment_rate:.4f} is outside (0, 1); "
                        "lower the expected_lift."
                    )
                effect_size = _cohens_h(baseline_rate, treatment_rate)
            else:
                raise ValueError(
                    "For proportion metrics supply expected_lift OR "
                    "expected_treatment_rate."
                )
        else:
            effect_size = float("nan")

    kwargs: Dict[str, Any] = {"ratio": ratio, "alternative": alternative}
    if solve_for == "n":
        kwargs.update(alpha=alpha, power=power, effect_size=effect_size)
        result = engine.solve_power(nobs1=None, **kwargs)
        result = int(math.ceil(result))
    elif solve_for == "power":
        if nobs1 is None:
            raise ValueError("nobs1 is required when solve_for='power'")
        kwargs.update(alpha=alpha, nobs1=nobs1, effect_size=effect_size)
        result = float(engine.solve_power(power=None, **kwargs))
    elif solve_for == "alpha":
        if nobs1 is None:
            raise ValueError("nobs1 is required when solve_for='alpha'")
        kwargs.update(nobs1=nobs1, power=power, effect_size=effect_size)
        result = float(engine.solve_power(alpha=None, **kwargs))
    elif solve_for == "effect_size":
        if nobs1 is None:
            raise ValueError("nobs1 is required when solve_for='effect_size'")
        kwargs.update(alpha=alpha, nobs1=nobs1, power=power)
        result = float(engine.solve_power(effect_size=None, **kwargs))
    else:
        # Unreachable, but keeps type checkers happy.
        raise AssertionError("unreachable")

    out: Dict[str, Any] = {
        "metric_type": metric_type,
        "solve_for": solve_for,
        "solved_value": result,
        "effect_size": effect_size,
        "alpha": alpha,
        "power": power if solve_for != "power" else result,
        "nobs1": nobs1 if solve_for != "n" else result,
        "ratio": ratio,
        "alternative": alternative,
    }
    if metric_type == "continuous":
        out.update(
            baseline_mean=baseline_mean,
            baseline_sd=baseline_sd,
            expected_lift=expected_lift,
            cohen_d=effect_size,
        )
    else:
        out.update(
            baseline_rate=baseline_rate,
            expected_treatment_rate=expected_treatment_rate
            if expected_treatment_rate is not None
            else baseline_rate + (expected_lift or 0.0),
            cohen_h=effect_size,
        )
    return out


# ---------------------------------------------------------------------------
# 2. Sample size for continuous / proportion
# ---------------------------------------------------------------------------


def required_sample_size(
    metric_type: str = "auto",
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    baseline_rate: Optional[float] = None,
    expected_lift: Optional[float] = None,
    expected_treatment_rate: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.8,
    ratio: float = 1.0,
    alternative: str = "two-sided",
) -> Dict[str, Any]:
    """
    A priori power analysis — solve for required sample size per arm.

    Convenience wrapper around :func:`solve_power` with ``solve_for='n'``.
    """
    return solve_power(
        solve_for="n",
        metric_type=metric_type,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        baseline_rate=baseline_rate,
        expected_lift=expected_lift,
        expected_treatment_rate=expected_treatment_rate,
        alpha=alpha,
        power=power,
        ratio=ratio,
        alternative=alternative,
    )


# ---------------------------------------------------------------------------
# 3. Minimum detectable effect (sensitivity)
# ---------------------------------------------------------------------------


def minimum_detectable_effect(
    nobs1: int,
    metric_type: str = "auto",
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    baseline_rate: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.8,
    ratio: float = 1.0,
    alternative: str = "two-sided",
) -> Dict[str, Any]:
    """
    Sensitivity analysis — given fixed sample size, return the minimum
    detectable effect (standardized + raw).
    """
    res = solve_power(
        solve_for="effect_size",
        metric_type=metric_type,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        baseline_rate=baseline_rate,
        alpha=alpha,
        power=power,
        ratio=ratio,
        alternative=alternative,
        nobs1=nobs1,
    )
    # For solve_for='effect_size', ``solved_value`` is the positive
    # standardized effect magnitude; ``res['effect_size']`` is a sentinel
    # NaN used internally. Use solved_value for downstream inversion.
    effect_size = abs(float(res["solved_value"]))
    metric_type = res["metric_type"]
    if metric_type == "continuous":
        # Cohen's d × pooled SD = absolute mean difference.
        if baseline_sd is None:
            raise ValueError("baseline_sd required for continuous MDE")
        absolute_lift = effect_size * baseline_sd
        relative_lift = (
            absolute_lift / baseline_mean if baseline_mean not in (0, 0.0) else None
        )
    else:
        # For proportion metrics, the standardized effect is Cohen's h;
        # invert it to recover an absolute rate change.
        # h ≈ 2(arcsin(sqrt(p2)) - arcsin(sqrt(p1)))
        # we report the absolute lift directly assuming small effect.
        if baseline_rate is None:
            raise ValueError("baseline_rate required for proportion MDE")
        # Approximate inversion via numerical search.
        from scipy.optimize import brentq

        def f(p2: float) -> float:
            return _cohens_h(baseline_rate, p2) - effect_size

        # Construct a sensible bracket. Statsmodels' NormalIndPower returns
        # only positive Cohen's h magnitudes, so the inversion is guaranteed
        # on the upper side (treatment_rate >= baseline_rate).
        absolute_lift: Optional[float] = None
        relative_lift: Optional[float] = None
        candidates = [
            (max(1e-6, baseline_rate + 1e-4), min(1 - 1e-6, baseline_rate + 0.5)),
            (max(1e-6, baseline_rate + 1e-4), min(1 - 1e-6, baseline_rate + 0.20)),
            (max(1e-6, baseline_rate + 1e-4), min(1 - 1e-6, baseline_rate + 0.10)),
            (max(1e-6, baseline_rate + 1e-4), min(1 - 1e-6, baseline_rate + 0.05)),
        ]
        for lo, hi in candidates:
            try:
                treatment_rate = brentq(f, lo, hi)
                absolute_lift = treatment_rate - baseline_rate
                relative_lift = absolute_lift / baseline_rate
                break
            except (ValueError, RuntimeError):
                continue

    return {
        "nobs1": nobs1,
        "metric_type": metric_type,
        "effect_size": effect_size,
        "absolute_lift": absolute_lift,
        "relative_lift": relative_lift,
        "alpha": alpha,
        "power": power,
        "ratio": ratio,
    }


# ---------------------------------------------------------------------------
# 4. Runtime estimation
# ---------------------------------------------------------------------------


def estimate_runtime_days(
    required_n_per_arm: int,
    daily_traffic: int,
    num_arms: int = 2,
    traffic_allocation: float = 1.0,
    ramp_up_days: int = 0,
) -> Dict[str, Any]:
    """
    Estimate how many days an experiment needs to run.

    Parameters
    ----------
    required_n_per_arm : int
        Sample size needed per arm (output of :func:`required_sample_size`).
    daily_traffic : int
        Average users/units entering the experiment per day.
    num_arms : int, default 2
        Number of variants (control + treatments).
    traffic_allocation : float, default 1.0
        Fraction of total traffic routed into the experiment (0-1).
    ramp_up_days : int, default 0
        Days where traffic ramps from 0 to full allocation.

    Returns
    -------
    dict with required_n_per_arm, num_arms, total_required_n,
    daily_eligible_users, days_needed (ceiling), breakdown.
    """
    if daily_traffic <= 0:
        raise ValueError("daily_traffic must be positive")
    if not (0 < traffic_allocation <= 1):
        raise ValueError("traffic_allocation must be in (0, 1]")
    if num_arms < 2:
        raise ValueError("num_arms must be >= 2")

    daily_eligible = daily_traffic * traffic_allocation
    total_required = required_n_per_arm * num_arms
    days_main = math.ceil(total_required / daily_eligible)
    total_days = days_main + max(ramp_up_days, 0)
    return {
        "required_n_per_arm": required_n_per_arm,
        "num_arms": num_arms,
        "total_required_n": total_required,
        "daily_traffic": daily_traffic,
        "traffic_allocation": traffic_allocation,
        "daily_eligible_users": int(round(daily_eligible)),
        "days_main": days_main,
        "ramp_up_days": max(ramp_up_days, 0),
        "days_needed": total_days,
    }


# ---------------------------------------------------------------------------
# 5. Stratification suggestion
# ---------------------------------------------------------------------------


def suggest_stratification(
    data: pd.DataFrame,
    group_column: Optional[str] = None,
    candidate_columns: Optional[Sequence[str]] = None,
    max_cardinality: int = 20,
) -> Dict[str, Any]:
    """
    Suggest columns to stratify randomisation on.

    A column is a good stratification candidate if:
      * its cardinality is between 2 and ``max_cardinality`` (incl.)
      * its distribution is highly skewed (top bucket >40% of rows) OR
        it is associated with the outcome metric / group column
        (chi-square independence test, p<0.1)

    Parameters
    ----------
    data : pd.DataFrame
        Historical dataset used to assess candidate columns.
    group_column : str, optional
        If provided, columns whose distribution differs across groups
        (via chi-square) are scored higher.
    candidate_columns : sequence of str, optional
        Limit assessment to these columns.  Defaults to every column.

    Returns
    -------
    dict with ``recommendations``: list of {column, score, reason}.
    """
    from scipy import stats as scipy_stats

    cols = list(candidate_columns) if candidate_columns else list(data.columns)
    if group_column and group_column in cols:
        cols.remove(group_column)

    recommendations: List[Dict[str, Any]] = []
    for col in cols:
        if col not in data.columns:
            continue
        series = data[col].dropna()
        if series.empty:
            continue
        nunique = int(series.nunique())
        if nunique < 2 or nunique > max_cardinality:
            continue

        # Skewness heuristic: top bucket share.
        vc = series.value_counts(normalize=True)
        top_share = float(vc.iloc[0]) if len(vc) else 0.0
        skew_score = 1.0 if top_share > 0.40 else 0.0

        # Independence from group column.
        group_p: Optional[float] = None
        if group_column and group_column in data.columns:
            cross = pd.crosstab(
                data[col].fillna("__nan__"), data[group_column].fillna("__nan__")
            )
            if cross.shape == (nunique, data[group_column].nunique()) and nunique > 1:
                try:
                    _, p, _, _ = scipy_stats.chi2_contingency(cross)
                    group_p = float(p)
                except ValueError:
                    group_p = None

        reason_parts: List[str] = []
        if skew_score:
            reason_parts.append(
                f"top bucket share {top_share:.0%} suggests imbalance risk"
            )
        if group_p is not None and group_p < 0.10:
            reason_parts.append(
                f"associated with {group_column} (chi-square p={group_p:.3f})"
            )
        if not reason_parts:
            continue

        # Score = how strongly recommended.
        score = 0.0
        if skew_score:
            score += top_share
        if group_p is not None and group_p < 0.10:
            score += -math.log10(max(group_p, 1e-6)) / 5  # smaller p → higher score

        recommendations.append(
            {
                "column": col,
                "cardinality": nunique,
                "top_bucket_share": round(top_share, 4),
                "group_chi2_p": round(group_p, 6) if group_p is not None else None,
                "score": round(float(score), 4),
                "reason": "; ".join(reason_parts),
            }
        )

    recommendations.sort(key=lambda r: r["score"], reverse=True)
    return {"recommendations": recommendations}


# ---------------------------------------------------------------------------
# 6. High-level design façade
# ---------------------------------------------------------------------------


def design_experiment(
    metric_type: str = "auto",
    baseline_mean: Optional[float] = None,
    baseline_sd: Optional[float] = None,
    baseline_rate: Optional[float] = None,
    expected_lift: Optional[float] = None,
    expected_treatment_rate: Optional[float] = None,
    alpha: float = 0.05,
    power: float = 0.8,
    ratio: float = 1.0,
    num_arms: int = 2,
    daily_traffic: Optional[int] = None,
    traffic_allocation: float = 1.0,
    ramp_up_days: int = 0,
    historical_data: Optional[pd.DataFrame] = None,
    stratification_group_column: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One-shot experiment design.

    Combines a priori power analysis, runtime estimation and (optionally)
    stratification suggestion into a single artifact.
    """
    sample_size = required_sample_size(
        metric_type=metric_type,
        baseline_mean=baseline_mean,
        baseline_sd=baseline_sd,
        baseline_rate=baseline_rate,
        expected_lift=expected_lift,
        expected_treatment_rate=expected_treatment_rate,
        alpha=alpha,
        power=power,
        ratio=ratio,
    )

    design: Dict[str, Any] = {
        "sample_size": sample_size,
        "design_inputs": {
            "metric_type": sample_size["metric_type"],
            "alpha": alpha,
            "power": power,
            "ratio": ratio,
            "num_arms": num_arms,
        },
    }

    if daily_traffic is not None and daily_traffic > 0:
        design["runtime"] = estimate_runtime_days(
            required_n_per_arm=int(sample_size["solved_value"]),
            daily_traffic=daily_traffic,
            num_arms=num_arms,
            traffic_allocation=traffic_allocation,
            ramp_up_days=ramp_up_days,
        )

    if historical_data is not None:
        design["stratification"] = suggest_stratification(
            historical_data,
            group_column=stratification_group_column,
        )

    return design


__all__ = [
    "solve_power",
    "required_sample_size",
    "minimum_detectable_effect",
    "estimate_runtime_days",
    "suggest_stratification",
    "design_experiment",
    "POWER_ANALYSIS_TOOL_NAMES",
]


POWER_ANALYSIS_TOOL_NAMES = [
    "pa_solve_power",
    "pa_required_sample_size",
    "pa_minimum_detectable_effect",
    "pa_estimate_runtime",
    "pa_suggest_stratification",
    "pa_design_experiment",
]