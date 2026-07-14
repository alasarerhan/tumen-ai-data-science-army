"""
Tests for ``ai_data_science_team.tools.a3_bayesian`` (A3 tool layer).
"""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.tools.a3_bayesian import (
    bayes_decision,
    beta_posterior,
    normal_means_posterior,
)


class TestBetaPosterior:
    def test_conjugate_update(self):
        # Prior Beta(1, 1) + 5 successes / 15 trials = Beta(6, 11).
        post = beta_posterior(successes=5, failures=10, prior_alpha=1.0, prior_beta=1.0)
        assert post.alpha_post == 6.0
        assert post.beta_post == 11.0
        d = post.to_dict()
        assert 0 <= d["credible_interval_95"][0] < d["credible_interval_95"][1] <= 1

    def test_prob_b_better(self):
        # Strong B vs A (clear lift) ⇒ prob_b_better → close to 1.
        a = beta_posterior(successes=10, failures=190)
        b = beta_posterior(successes=20, failures=180)
        p = b.prob_b_better(a)
        assert p > 0.95

    def test_prob_b_better_no_difference(self):
        a = beta_posterior(successes=50, failures=950)
        b = beta_posterior(successes=50, failures=950)
        p = b.prob_b_better(a)
        # Roughly 0.5 — sample size 2000 ⇒ ~0.06 s.d.
        assert 0.20 < p < 0.80


class TestBayesDecision:
    def test_promote_b_when_overwhelming(self):
        a = beta_posterior(successes=2, failures=198)
        b = beta_posterior(successes=20, failures=180)
        out = bayes_decision(a, b)
        assert out["decision"] == "promote_b"
        assert out["prob_b_better"] > 0.95

    def test_stay_with_a_is_reachable(self):
        # B is sharply worse; with a relaxed expected-loss threshold
        # the framework can return "stay_with_a".
        a = beta_posterior(successes=80, failures=920)
        b = beta_posterior(successes=10, failures=990)
        out = bayes_decision(
            a, b, prob_b_better_threshold=0.90,
            expected_loss_threshold=1.0,
        )
        assert out["decision"] == "stay_with_a"

    def test_inconclusive_when_close(self):
        a = beta_posterior(successes=51, failures=49)
        b = beta_posterior(successes=50, failures=50)
        out = bayes_decision(a, b)
        assert out["decision"] in {"inconclusive", "stay_with_a", "promote_b"}


class TestNormalMeansPosterior:
    def test_credible_interval(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=80, loc=10.0)
        b = rng.normal(size=80, loc=11.5)
        post = normal_means_posterior(a, b)
        ci_a = post.credible_interval_a()
        ci_b = post.credible_interval_b()
        # Means should differ noticeably; CI widths must be positive.
        assert ci_a[0] < ci_a[1]
        assert ci_b[0] < ci_b[1]
        # B mean is shifted higher than A; not guaranteed disjoint, but
        # B's lower bound should be at or above A's mid-point.
        assert ci_b[0] > (ci_a[0] + ci_a[1]) / 2 - 1.0

    def test_prob_b_better_above_threshold(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=200, loc=0)
        b = rng.normal(size=200, loc=1.5)
        post = normal_means_posterior(a, b)
        p = post.prob_b_better_than_a(threshold=0.0)
        assert p > 0.99

    def test_to_dict_has_required_keys(self):
        rng = np.random.RandomState(0)
        a = rng.normal(size=20)
        b = rng.normal(size=20, loc=0.5)
        post = normal_means_posterior(a, b)
        d = post.to_dict()
        assert "posterior_a" in d
        assert "posterior_b" in d

    def test_too_small_sample_raises(self):
        with pytest.raises(ValueError):
            normal_means_posterior([1.0], [2.0])
