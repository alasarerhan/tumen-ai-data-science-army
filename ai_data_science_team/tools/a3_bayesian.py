"""
a3_bayesian
===========

Deterministic Bayesian A/B / proportion / continuous tools supporting
**A3 — Bayesian Analysis** (spec ``docs/specs/A3-bayesian-analysis.md``).

Implements conjugate-prior posterior updates for proportions and
Gaussian means so the agent can answer questions like
``P(B > A)``, credible intervals, and expected loss without external
samplers.

Public surface
--------------

* :func:`beta_posterior` — Beta-Binomial posterior + decision rules.
* :func:`normal_means_posterior` — normal-normal conjugate update.
* :func:`bayes_decision` — choose A vs B based on
  ``P(B>A)`` + expected-loss threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import lgamma
from typing import Any, Dict, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _log_beta(a: float, b: float) -> float:
    return float(lgamma(a) + lgamma(b) - lgamma(a + b))


def _log_comb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return float(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1))


def _expit(x: float) -> float:
    if x >= 0:
        z = float(np.exp(-x))
        return 1.0 / (1.0 + z)
    z = float(np.exp(x))
    return z / (1.0 + z)


# ---------------------------------------------------------------------------
# Beta-Binomial
# ---------------------------------------------------------------------------


@dataclass
class BetaPosterior:
    alpha_post: float
    beta_post: float
    samples_a: int
    samples_b: int
    successes_a: int
    successes_b: int

    def credible_interval(self, mass: float = 0.95) -> Tuple[float, float]:
        """Two-sided credible interval at the given mass."""
        from scipy.stats import beta as beta_dist

        lo = float(beta_dist.ppf((1 - mass) / 2, self.alpha_post, self.beta_post))
        hi = float(beta_dist.ppf(1 - (1 - mass) / 2, self.alpha_post, self.beta_post))
        return (lo, hi)

    def prob_b_better(self, other: "BetaPosterior") -> float:
        """P(self > other) under two independent beta posteriors."""
        from scipy.stats import beta as beta_dist

        # Monte-Carlo is the standard way without a closed-form integral.
        rng = np.random.default_rng(0)
        self_samples = beta_dist.rvs(self.alpha_post, self.beta_post, size=20000, random_state=rng)
        other_samples = beta_dist.rvs(other.alpha_post, other.beta_post, size=20000, random_state=rng)
        return float(np.mean(self_samples > other_samples))

    def expected_loss(self, other: "BetaPosterior", *, threshold: float = 0.0) -> float:
        """Expected loss of choosing ``other`` over ``self`` for unit value.

        Uses Monte Carlo over the posterior of (other - self).
        """
        from scipy.stats import beta as beta_dist

        rng = np.random.default_rng(0)
        a = beta_dist.rvs(self.alpha_post, self.beta_post, size=20000, random_state=rng)
        b = beta_dist.rvs(other.alpha_post, other.beta_post, size=20000, random_state=rng)
        diff = b - a
        # Loss if diff < threshold: |threshold - diff|; otherwise 0.
        loss = np.maximum(0.0, threshold - diff)
        return float(np.mean(loss))

    def to_dict(self) -> Dict[str, Any]:
        ci = self.credible_interval()
        return {
            "alpha_post": self.alpha_post,
            "beta_post": self.beta_post,
            "credible_interval_95": [ci[0], ci[1]],
        }


def beta_posterior(
    successes: int,
    failures: int,
    *,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
) -> "BetaPosterior":
    """Compute the Beta-Binomial posterior parameters.

    Beta(α₀, β₀) prior + binomial(s, f) likelihood → Beta(α₀+s, β₀+f).
    """
    alpha_post = prior_alpha + successes
    beta_post = prior_beta + failures
    return BetaPosterior(
        alpha_post=alpha_post,
        beta_post=beta_post,
        samples_a=successes + failures,
        samples_b=0,
        successes_a=successes,
        successes_b=0,
    )


def bayes_decision(
    posterior_a: BetaPosterior,
    posterior_b: BetaPosterior,
    *,
    prob_b_better_threshold: float = 0.95,
    expected_loss_threshold: float = 0.001,
    prob_b_better_samples: int = 20000,
) -> Dict[str, Any]:
    """Pick A or B by posterior evidence.

    Decision rule: choose B if ``P(B > A) > prob_b_better_threshold``
    AND ``expected_loss < expected_loss_threshold``.  Otherwise stay
    with A or call it inconclusive.
    """
    rng = np.random.default_rng(0)
    from scipy.stats import beta as beta_dist

    a_s = beta_dist.rvs(
        posterior_a.alpha_post,
        posterior_a.beta_post,
        size=int(prob_b_better_samples),
        random_state=rng,
    )
    b_s = beta_dist.rvs(
        posterior_b.alpha_post,
        posterior_b.beta_post,
        size=int(prob_b_better_samples),
        random_state=rng,
    )
    prob_b = float(np.mean(b_s > a_s))
    exp_loss = float(np.mean(np.maximum(0.0, a_s - b_s)))

    if prob_b > prob_b_better_threshold and exp_loss < expected_loss_threshold:
        decision = "promote_b"
        rationale = (
            f"P(B>A)={prob_b:.3f} above {prob_b_better_threshold} "
            f"and expected loss ({exp_loss:.4f}) below the threshold."
        )
    elif 1 - prob_b > prob_b_better_threshold and exp_loss < expected_loss_threshold:
        decision = "stay_with_a"
        rationale = (
            f"P(A>B)={1 - prob_b:.3f} above the threshold; "
            f"B does not yet meaningfully beat A."
        )
    else:
        decision = "inconclusive"
        rationale = (
            f"P(B>A)={prob_b:.3f}; expected loss={exp_loss:.4f}. "
            "Not enough evidence to declare a winner."
        )
    return {
        "decision": decision,
        "rationale": rationale,
        "prob_b_better": prob_b,
        "expected_loss_b_over_a": exp_loss,
    }


# ---------------------------------------------------------------------------
# Normal means
# ---------------------------------------------------------------------------


@dataclass
class NormalMeansPosterior:
    n_a: int
    n_b: int
    sum_a: float
    sum_b: float
    var_a: float
    var_b: float
    prior_mean: float = 0.0
    prior_var: float = 1e6

    def posterior_params_a(self) -> Tuple[float, float]:
        prior_precision = 1.0 / self.prior_var
        like_precision_a = self.n_a / max(self.var_a, 1e-12)
        post_precision_a = prior_precision + like_precision_a
        post_mean_a = (
            prior_precision * self.prior_mean
            + like_precision_a * (self.sum_a / max(self.n_a, 1))
        ) / post_precision_a
        return float(post_mean_a), float(1.0 / post_precision_a)

    def posterior_params_b(self) -> Tuple[float, float]:
        prior_precision = 1.0 / self.prior_var
        like_precision_b = self.n_b / max(self.var_b, 1e-12)
        post_precision_b = prior_precision + like_precision_b
        post_mean_b = (
            prior_precision * self.prior_mean
            + like_precision_b * (self.sum_b / max(self.n_b, 1))
        ) / post_precision_b
        return float(post_mean_b), float(1.0 / post_precision_b)

    def credible_interval_a(self, mass: float = 0.95) -> Tuple[float, float]:
        from scipy.stats import norm

        mu, var = self.posterior_params_a()
        z = float(norm.ppf(1 - (1 - mass) / 2))
        return (mu - z * var ** 0.5, mu + z * var ** 0.5)

    def credible_interval_b(self, mass: float = 0.95) -> Tuple[float, float]:
        from scipy.stats import norm

        mu, var = self.posterior_params_b()
        z = float(norm.ppf(1 - (1 - mass) / 2))
        return (mu - z * var ** 0.5, mu + z * var ** 0.5)

    def prob_b_better_than_a(self, threshold: float = 0.0) -> float:
        """P(B - A > threshold) using the analytic posterior of the
        difference of two normal random variables.
        """
        from scipy.stats import norm

        mu_a, var_a = self.posterior_params_a()
        mu_b, var_b = self.posterior_params_b()
        mu_diff = mu_b - mu_a
        var_diff = var_a + var_b
        if var_diff <= 0:
            return 1.0 if mu_diff > threshold else 0.0
        sigma = float(var_diff) ** 0.5
        return float(1 - norm.cdf((threshold - mu_diff) / sigma))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "posterior_a": self.posterior_params_a(),
            "posterior_b": self.posterior_params_b(),
            "credible_interval_a_95": list(self.credible_interval_a()),
            "credible_interval_b_95": list(self.credible_interval_b()),
        }


def normal_means_posterior(
    samples_a: Sequence[float],
    samples_b: Sequence[float],
    *,
    prior_mean: float = 0.0,
    prior_var: float = 1e6,
) -> NormalMeansPosterior:
    """Build a normal-normal conjugate posterior for two samples.

    Pooled variance is supplied per-sample; the conjugate posterior
    uses ``1/var_i`` weighting with a weak non-informative prior.
    """
    arr_a = np.asarray(list(samples_a), dtype=float)
    arr_b = np.asarray(list(samples_b), dtype=float)
    if arr_a.size < 2 or arr_b.size < 2:
        raise ValueError("need at least two observations per arm")
    var_a = float(np.var(arr_a, ddof=1))
    var_b = float(np.var(arr_b, ddof=1))
    return NormalMeansPosterior(
        n_a=int(arr_a.size),
        n_b=int(arr_b.size),
        sum_a=float(np.sum(arr_a)),
        sum_b=float(np.sum(arr_b)),
        var_a=var_a,
        var_b=var_b,
        prior_mean=prior_mean,
        prior_var=prior_var,
    )


__all__ = [
    "beta_posterior",
    "BetaPosterior",
    "bayes_decision",
    "normal_means_posterior",
    "NormalMeansPosterior",
]


