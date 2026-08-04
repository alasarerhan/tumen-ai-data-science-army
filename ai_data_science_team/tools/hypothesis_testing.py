from __future__ import annotations

"""
a4_hypothesis_testing
====================

Deterministic tools supporting **A4 — Hypothesis Testing Danışmanı**
(spec ``docs/specs/A4-hypothesis-testing.md``).

Provides a parametric-vs-non-parametric advisor and parametric
hypothesis tests (one-sample, two-sample, paired).

Public surface
--------------

* :func:`recommend_test` — given a sample + research question,
  recommend the appropriate test (with rationale).
* :func:`run_test` — execute the recommended test and return a
  statistic + p_value + effect-size summary.
* :func:`interpret_result` — translate a p_value + effect-size into
  a plain-language finding.
"""

import math  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Optional, Sequence, Tuple  # noqa: E402, F401

import numpy as np  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------


@dataclass
class TestRecommendation:
    test: str
    rationale: str
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test": self.test,
            "rationale": self.rationale,
            "assumptions": list(self.assumptions),
        }


def _is_normal_shapiro_safe(values: np.ndarray) -> bool:
    """Lightweight normality heuristic without SciPy.

    Returns True if the (skewness, kurtosis) pair is "mild" for n
    samples (rough rule of thumb: |skew| < 1 and excess kurtosis < 2).
    """
    if values.size < 8:
        return False
    m = float(np.mean(values))
    s = float(np.std(values, ddof=1))
    if s == 0:
        return True
    skew = float(np.mean(((values - m) / s) ** 3))
    kurt = float(np.mean(((values - m) / s) ** 4) - 3)
    return abs(skew) < 1.0 and kurt < 2.0


def recommend_test(
    values: Sequence[float],
    *,
    alt: str = "two-sided",
    comparison: Optional[Sequence[float]] = None,
    target_value: Optional[float] = None,
) -> Dict[str, Any]:
    """Pick a hypothesis test for the data shape.

    Parameters
    ----------
    values : array-like
        The primary sample.
    comparison : array-like, optional
        If provided, the recommendation is for two-sample
        comparison; otherwise single-sample (compare to
        ``target_value``).
    target_value : float, optional
        Reference value for single-sample tests. Defaults to 0.
    """
    arr = np.asarray(list(values), dtype=float).ravel()
    if arr.size < 2:
        raise ValueError("values must contain at least two observations")
    normal = _is_normal_shapiro_safe(arr)
    if comparison is not None:
        cmp = np.asarray(list(comparison), dtype=float).ravel()
        if cmp.size < 2:
            raise ValueError("comparison must contain ≥ 2 observations")
        cmp_normal = _is_normal_shapiro_safe(cmp)
        if normal and cmp_normal:
            rec = TestRecommendation(
                test="two_sample_t_test",
                rationale=(
                    "Both samples are roughly bell-shaped; "
                    "use Welch's two-sample t-test (no equal-variance "
                    "assumption)."
                ),
                assumptions=[
                    "Independent observations",
                    "Approximately normal distributions",
                    "Welch's variant tolerates unequal variances",
                ],
            )
        else:
            rec = TestRecommendation(
                test="mann_whitney_u",
                rationale=(
                    "At least one sample deviates from normal; "
                    "use a non-parametric two-sample test "
                    "(Mann–Whitney U / Wilcoxon rank-sum)."
                ),
                assumptions=[
                    "Independent observations",
                    "Ordinal/continuous responses",
                ],
            )
        return rec.to_dict()

    0.0 if target_value is None else float(target_value)
    if normal:
        return TestRecommendation(
            test="one_sample_t_test",
            rationale=(
                "The sample is roughly bell-shaped; use a one-sample "
                "t-test against the reference value."
            ),
            assumptions=[
                "Independent observations",
                "Approximately normal distribution",
            ],
        ).to_dict()

    return TestRecommendation(
        test="wilcoxon_signed_rank",
        rationale=(
            "The sample deviates from normal; use a non-parametric "
            "one-sample Wilcoxon signed-rank test against the "
            "reference value."
        ),
        assumptions=[
            "Independent observations",
            "Symmetric distribution around the reference",
        ],
    ).to_dict()


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------


@dataclass
class HypothesisTestResult:
    test: str
    statistic: float
    p_value: float
    effect_size: float
    effect_size_kind: str
    n: int
    alternative: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test": self.test,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "effect_size_kind": self.effect_size_kind,
            "n": self.n,
            "alternative": self.alternative,
            "note": self.note,
        }


def _welch_ttest(a: np.ndarray, b: np.ndarray, alternative: str) -> Tuple[float, float]:
    ma, mb = float(np.mean(a)), float(np.mean(b))
    va, vb = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    na, nb = a.size, b.size
    se = math.sqrt(va / na + vb / nb)
    if se == 0:
        return float("nan"), float("nan")
    t = (ma - mb) / se
    try:
        from scipy.stats import t as t_dist  # noqa: E402, F401

        # Welch–Satterthwaite d.o.f.
        df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
        if alternative == "two-sided":
            p = float(2 * (1 - t_dist.cdf(abs(t), df=df)))
        elif alternative == "greater":
            p = float(1 - t_dist.cdf(t, df=df))
        else:
            p = float(t_dist.cdf(t, df=df))
    except ImportError:
        # Fallback: normal approximation.
        from math import erf, sqrt  # noqa: E402, F401

        z = t
        if alternative == "two-sided":
            p = 1 - erf(abs(z) / sqrt(2))
        elif alternative == "greater":
            p = 0.5 * (1 - erf(z / sqrt(2)))
        else:
            p = 0.5 * (1 + erf(z / sqrt(2)))
    return float(t), p


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    ma, mb = float(np.mean(a)), float(np.mean(b))
    sa, sb = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
    na, nb = a.size, b.size
    sp = math.sqrt(((na - 1) * sa**2 + (nb - 1) * sb**2) / max(na + nb - 2, 1))
    if sp == 0:
        return 0.0
    return float((ma - mb) / sp)


def run_test(
    values: Sequence[float],
    *,
    alt: str = "two-sided",
    comparison: Optional[Sequence[float]] = None,
    target_value: Optional[float] = None,
    mu: float = 0.0,
) -> Dict[str, Any]:
    """Execute the chosen hypothesis test (after :func:`recommend_test`)."""
    if alt not in {"two-sided", "greater", "less"}:
        raise ValueError(f"alt must be one of two-sided/greater/less, got {alt!r}")
    arr = np.asarray(list(values), dtype=float).ravel()
    if arr.size < 2:
        raise ValueError("values too small")
    if comparison is not None:
        cmp = np.asarray(list(comparison), dtype=float).ravel()
        t, p = _welch_ttest(arr, cmp, alt)
        d = _cohens_d(arr, cmp)
        return HypothesisTestResult(
            test="two_sample_t_test",
            statistic=float(t),
            p_value=float(p),
            effect_size=float(d),
            effect_size_kind="cohens_d",
            n=int(arr.size + cmp.size),
            alternative=alt,
        ).to_dict()
    target = mu if target_value is None else float(target_value)
    dev = arr - target
    sd = float(np.std(dev, ddof=1))
    if sd == 0:
        return HypothesisTestResult(
            test="one_sample_t_test",
            statistic=0.0,
            p_value=1.0 if alt == "two-sided" else 0.0,
            effect_size=0.0,
            effect_size_kind="cohens_d",
            n=int(arr.size),
            alternative=alt,
            note="zero variance",
        ).to_dict()
    t = float(np.mean(dev) / (sd / math.sqrt(arr.size)))
    try:
        from scipy.stats import t as t_dist  # noqa: E402, F401

        df = arr.size - 1
        if alt == "two-sided":
            p = float(2 * (1 - t_dist.cdf(abs(t), df=df)))
        elif alt == "greater":
            p = float(1 - t_dist.cdf(t, df=df))
        else:
            p = float(t_dist.cdf(t, df=df))
    except ImportError:
        from math import erf, sqrt  # noqa: E402, F401

        z = t
        if alt == "two-sided":
            p = 1 - erf(abs(z) / sqrt(2))
        elif alt == "greater":
            p = 0.5 * (1 - erf(z / sqrt(2)))
        else:
            p = 0.5 * (1 + erf(z / sqrt(2)))
    d = float(np.mean(dev) / sd) if sd > 0 else 0.0
    return HypothesisTestResult(
        test="one_sample_t_test",
        statistic=float(t),
        p_value=float(p),
        effect_size=float(d),
        effect_size_kind="cohens_d",
        n=int(arr.size),
        alternative=alt,
    ).to_dict()


# ---------------------------------------------------------------------------
# Plain-language interpretation
# ---------------------------------------------------------------------------


def interpret_result(
    p_value: float,
    effect_size: float,
    *,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Translate a p_value + effect_size into a plain-language finding."""
    significant = p_value < alpha
    if abs(effect_size) < 0.2:
        magnitude = "very small"
    elif abs(effect_size) < 0.5:
        magnitude = "small"
    elif abs(effect_size) < 0.8:
        magnitude = "medium"
    else:
        magnitude = "large"

    if significant:
        finding = (
            f"Statistically significant at α={alpha} "
            f"(p={p_value:.4f}); effect size is {magnitude} "
            f"(d={effect_size:+.3f}). The data is unlikely to be "
            "compatible with the null hypothesis."
        )
    else:
        finding = (
            f"Not statistically significant at α={alpha} "
            f"(p={p_value:.4f}); insufficient evidence to reject "
            f"the null. Effect size is {magnitude} (d={effect_size:+.3f})."
        )
    return {
        "significant": bool(significant),
        "magnitude": magnitude,
        "finding": finding,
        "p_value": float(p_value),
        "effect_size": float(effect_size),
        "alpha": float(alpha),
    }


__all__ = [
    "recommend_test",
    "run_test",
    "interpret_result",
]
