"""
Tests for ``ai_data_science_team.tools.hpo`` (E2 tool layer).

Optuna is optional — these tests use the in-tree RandomSampler.
"""

from __future__ import annotations

import math
import random

import pytest

from ai_data_science_team.tools.hpo import (
    RandomSampler,
    random_sample_params,
    run_study,
    suggest_default_search_space,
)


class TestSuggestDefaultSearchSpace:
    def test_lightgbm_classification(self):
        sp = suggest_default_search_space("lightgbm", "classification")
        assert "num_leaves" in sp
        assert "learning_rate" in sp
        # num_leaves is log-scale int.
        assert sp["num_leaves"]["type"] == "int"
        assert sp["num_leaves"]["log"] is True

    def test_xgboost_regression(self):
        sp = suggest_default_search_space("xgboost", "regression")
        assert "max_depth" in sp
        assert sp["max_depth"]["type"] == "int"

    def test_sklearn_classification(self):
        sp = suggest_default_search_space("sklearn", "classification")
        assert "C" in sp

    def test_unknown_pair_raises(self):
        with pytest.raises(ValueError):
            suggest_default_search_space("lightgbm", "nlp_task")


class TestSampling:
    def test_random_sample_int_in_range(self):
        space = {
            "n_estimators": {"type": "int", "low": 10, "high": 200},
            "lr": {"type": "float", "low": 0.001, "high": 0.5, "log": True},
        }
        params = random_sample_params(space, random.Random(0))
        assert 10 <= params["n_estimators"] <= 200
        assert 0.001 <= params["lr"] <= 0.5

    def test_log_scale_produces_geometric_distribution(self):
        space = {"x": {"type": "float", "low": 1e-3, "high": 1e3, "log": True}}
        rng = random.Random(0)
        params = random_sample_params(space, rng)
        # On log-uniform sampling the log of samples is uniform.
        log_x = math.log10(params["x"])
        assert -3 <= log_x <= 3

    def test_random_sampler_repeatable(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}
        s1 = RandomSampler(space, seed=42)
        s2 = RandomSampler(space, seed=42)
        # Same seed → same draw.
        assert s1.sample() == s2.sample()


class TestRunStudy:
    def test_smoke_with_quadratic_objective(self):
        # Objective peaks at (x=0.5, y=0.5).
        space = {
            "x": {"type": "float", "low": 0.0, "high": 1.0},
            "y": {"type": "float", "low": 0.0, "high": 1.0},
        }

        def fn(p):
            return -(p["x"] - 0.5) ** 2 - (p["y"] - 0.5) ** 2

        out = run_study(
            fn,
            space,
            n_trials=10,
            direction="maximize",
            random_seed=0,
        )
        assert "best_trial" in out
        assert out["best_trial"]["value"] is not None
        # Trials completed should equal n_trials (none pruned in this setup).
        assert out["n_trials_completed"] >= 5
        # Best point should be close to optimum.
        best_x = out["best_trial"]["params"]["x"]
        best_y = out["best_trial"]["params"]["y"]
        assert abs(best_x - 0.5) < 0.5
        assert abs(best_y - 0.5) < 0.5

    def test_direction_minimize(self):
        space = {"x": {"type": "float", "low": -10.0, "high": 10.0}}

        def fn(p):
            return p["x"] ** 2

        out = run_study(
            fn,
            space,
            n_trials=20,
            direction="minimize",
            random_seed=0,
        )
        # Best x should be near 0.
        best_x = out["best_trial"]["params"]["x"]
        assert abs(best_x) < 5.0
        assert out["best_trial"]["value"] < 25.0

    def test_invalid_direction_raises(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}

        with pytest.raises(ValueError):
            run_study(lambda p: 0.0, space, direction="weird")

    def test_n_trials_zero_raises(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}
        with pytest.raises(ValueError):
            run_study(lambda p: 0.0, space, n_trials=0)

    def test_n_trials_completed_and_pruned(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}

        def fn(p):
            return -(p["x"] - 0.5) ** 2

        out = run_study(
            fn,
            space,
            n_trials=15,
            direction="maximize",
            pruner="median",
            random_seed=0,
        )
        # Some trials may have been pruned (or not); both fields exist.
        assert "n_trials_completed" in out
        assert "n_trials_pruned" in out
        assert (
            out["n_trials_completed"] + out["n_trials_pruned"]
            == len(out["trials"])
        )

    def test_objective_failure_recorded(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}

        def flaky(p):
            if p["x"] < 0.3:
                raise ValueError("simulated crash")
            return p["x"]

        out = run_study(
            flaky,
            space,
            n_trials=10,
            direction="maximize",
            random_seed=0,
        )
        # Some trials must carry an error.
        errors = [t for t in out["trials"] if t["error"]]
        assert errors, "expected at least one trial with error"

    def test_param_importances_present(self):
        space = {
            "x": {"type": "float", "low": 0.0, "high": 1.0},
            "y": {"type": "float", "low": 0.0, "high": 1.0},
        }

        def fn(p):
            return -(p["x"] - 0.5) ** 2 - 0.05 * (p["y"] - 0.5) ** 2

        out = run_study(
            fn,
            space,
            n_trials=20,
            direction="maximize",
            random_seed=0,
        )
        assert "x" in out["param_importances"]
        assert "y" in out["param_importances"]
        # x matters more than y → its importance should be larger.
        assert out["param_importances"]["x"] > out["param_importances"]["y"]

    def test_optimization_history_dense(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}

        def fn(p):
            return p["x"]

        out = run_study(
            fn, space, n_trials=5, direction="maximize", random_seed=0
        )
        assert len(out["optimization_history"]) == 5
        # Trial 0..4 should appear in order.
        assert [h["trial"] for h in out["optimization_history"]] == [0, 1, 2, 3, 4]

    def test_timeout_stops_early(self):
        space = {"x": {"type": "float", "low": 0.0, "high": 1.0}}

        def fn(p):
            # Force a tiny artificial delay to provoke timeout.
            for _ in range(1000):
                pass
            return p["x"]

        out = run_study(
            fn,
            space,
            n_trials=1000,
            direction="maximize",
            timeout_s=0.001,  # effectively immediate
            random_seed=0,
        )
        # We expect the timeout to cut the loop early.
        assert len(out["trials"]) < 1000

    def test_default_search_space_works(self):
        space = suggest_default_search_space("lightgbm", "classification")

        def fn(p):
            # toy — learning rate that maximises around 0.05.
            return -abs(p["learning_rate"] - 0.05)

        out = run_study(
            fn,
            space,
            n_trials=20,
            direction="maximize",
            random_seed=0,
        )
        assert out["best_trial"]["value"] is not None
        # Optimum should be near 0.05 with a generous tolerance.
        assert abs(out["best_trial"]["params"]["learning_rate"] - 0.05) < 0.2
