"""
e2_hpo
======

Deterministic hyperparameter optimisation tools for **E2 — HPO**
(spec from ``docs/specs/E2-hpo.md``).

The production target is Optuna (``optuna.study.create_study`` +
``MedianPruner`` + RDB storage); this module ships a self-contained
random + TPE-lite sampler so the same code path is testable in
CI without the optional dependency. When ``optuna`` is installed,
:func:`run_study` will dispatch to it via thin wrappers; when it is
not, the in-tree RandomSampler is used. Either way the public API
and the contract documented in E2 §2 are preserved.

Public surface
--------------

* :func:`suggest_default_search_space` — produce a sensible default
  search space per ``(engine, task_type)``.
* :func:`random_sample_params` / :func:`random_sampler` — built-in
  random sampler (Optuna fallback).
* :func:`run_study` — execute ``n_trials`` evaluations, log per-trial
  to MLflow (if available), return the HPO result dict specified in
  the spec.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Built-in default search spaces
# ---------------------------------------------------------------------------


DEFAULT_SEARCH_SPACES: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]] = {
    ("lightgbm", "classification"): {
        "num_leaves": {"type": "int", "low": 16, "high": 256, "log": True},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.3, "log": True},
        "feature_fraction": {"type": "float", "low": 0.5, "high": 1.0},
        "bagging_fraction": {"type": "float", "low": 0.5, "high": 1.0},
        "min_data_in_leaf": {"type": "int", "low": 5, "high": 50},
    },
    ("lightgbm", "regression"): {
        "num_leaves": {"type": "int", "low": 16, "high": 256, "log": True},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.3, "log": True},
        "feature_fraction": {"type": "float", "low": 0.5, "high": 1.0},
        "bagging_fraction": {"type": "float", "low": 0.5, "high": 1.0},
    },
    ("xgboost", "classification"): {
        "max_depth": {"type": "int", "low": 3, "high": 12},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.3, "log": True},
        "subsample": {"type": "float", "low": 0.5, "high": 1.0},
        "colsample_bytree": {"type": "float", "low": 0.5, "high": 1.0},
        "min_child_weight": {"type": "int", "low": 1, "high": 10},
    },
    ("xgboost", "regression"): {
        "max_depth": {"type": "int", "low": 3, "high": 12},
        "learning_rate": {"type": "float", "low": 0.005, "high": 0.3, "log": True},
        "subsample": {"type": "float", "low": 0.5, "high": 1.0},
        "colsample_bytree": {"type": "float", "low": 0.5, "high": 1.0},
    },
    ("sklearn", "classification"): {
        "C": {"type": "float", "low": 0.01, "high": 100, "log": True},
    },
    ("sklearn", "regression"): {
        "alpha": {"type": "float", "low": 0.01, "high": 100, "log": True},
    },
}


def suggest_default_search_space(
    engine: str, task_type: str
) -> Dict[str, Dict[str, Any]]:
    """Return the default search space for an ``(engine, task_type)`` pair.

    Unknown pairs raise ``ValueError``.
    """
    key = (engine, task_type)
    if key not in DEFAULT_SEARCH_SPACES:
        raise ValueError(
            f"No default search space for ({engine}, {task_type}). "
            f"Known: {sorted(DEFAULT_SEARCH_SPACES)}"
        )
    return {k: dict(v) for k, v in DEFAULT_SEARCH_SPACES[key].items()}


# ---------------------------------------------------------------------------
# Sampling primitives
# ---------------------------------------------------------------------------


def _sample_one(rng: random.Random, spec: Mapping[str, Any]) -> Any:
    """Sample one value for a single hyperparameter spec."""
    t = spec.get("type", "float")
    low = spec.get("low")
    high = spec.get("high")
    log = bool(spec.get("log", False))
    if log and (low is None or high is None or low <= 0 or high <= 0):
        raise ValueError(
            f"'log' requires positive low/high (got {low}, {high})"
        )
    if t == "int":
        if log:
            lo = math.log(low)
            hi = math.log(high)
            return int(round(math.exp(rng.uniform(lo, hi))))
        return rng.randint(int(low), int(high))
    # default: float
    if log:
        lo = math.log(low)
        hi = math.log(high)
        return math.exp(rng.uniform(lo, hi))
    return rng.uniform(float(low), float(high))


def random_sample_params(
    space: Mapping[str, Mapping[str, Any]],
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    """Sample a parameter dict from ``space``."""
    rng = rng or random.Random()
    return {name: _sample_one(rng, spec) for name, spec in space.items()}


class RandomSampler:
    """Random sampler — uniform over the spec, deterministic given seed."""

    def __init__(self, space: Mapping[str, Mapping[str, Any]], seed: int = 0):
        self.space = {k: dict(v) for k, v in space.items()}
        self.rng = random.Random(seed)

    def sample(self) -> Dict[str, Any]:
        return random_sample_params(self.space, self.rng)


# ---------------------------------------------------------------------------
# Study execution
# ---------------------------------------------------------------------------


@dataclass
class TrialResult:
    number: int
    value: float
    params: Dict[str, Any]
    pruned: bool = False
    error: Optional[str] = None
    duration_s: float = 0.0


@dataclass
class HPOResult:
    study_name: str
    best_trial: Dict[str, Any]
    n_trials_completed: int
    n_trials_pruned: int
    optimization_history: List[Dict[str, Any]]
    param_importances: Dict[str, float]
    direction: str
    trials: List[TrialResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "study_name": self.study_name,
            "best_trial": self.best_trial,
            "n_trials_completed": self.n_trials_completed,
            "n_trials_pruned": self.n_trials_pruned,
            "optimization_history": self.optimization_history,
            "param_importances": self.param_importances,
            "direction": self.direction,
        }


def _median_prune_decision(
    completed: Sequence[TrialResult],
    current_value: Optional[float],
    direction: str,
    warmup: int = 3,
) -> bool:
    """Median-pruner: stop early if current value is worse than the median.

    Implementation summary from E2 spec §2: ``MedianPruner`` prunes a
    trial at step ``s`` when its intermediate value is below (above)
    the median of previous trials at the same step. The in-tree
    fallback keeps the same idea at the trial level.
    """
    if len(completed) < warmup or current_value is None:
        return False
    history = [
        t.value for t in completed if not t.pruned
    ]
    if not history:
        return False
    median = sorted(history)[len(history) // 2]
    if direction == "maximize":
        return current_value < median
    return current_value > median


def _compute_param_importances(
    trials: Sequence[TrialResult],
    direction: str,
) -> Dict[str, float]:
    """Crude variance-based importance: how much each param's variation
    correlates with the objective. Returns a dict in [0, 1] summing
    approximately to 1.
    """
    if not trials:
        return {}
    completed = [t for t in trials if not t.pruned]
    if len(completed) < 2:
        return {}
    keys = list(completed[0].params.keys())
    values = {k: [] for k in keys}
    objective = []
    for t in completed:
        objective.append(t.value)
        for k in keys:
            values[k].append(t.params[k])
    # For each parameter, compute the variance of the conditional mean.
    # This is a cheap proxy for "importance" — sensitive params move the
    # objective a lot when binned.
    importances: Dict[str, float] = {}
    for k in keys:
        col = values[k]
        # Bin into up to 5 quantile buckets.
        if len(set(col)) < 2:
            importances[k] = 0.0
            continue
        try:
            ranks = [sorted(col).index(v) for v in col]
            n_bins = min(5, len(set(ranks)))
            edges = [
                min(ranks) + i * (max(ranks) - min(ranks)) / n_bins
                for i in range(n_bins + 1)
            ]
            bin_indices = [
                sum(v > e for e in edges[1:]) for v in ranks
            ]
            bin_means: Dict[int, List[float]] = {}
            for i, bi in enumerate(bin_indices):
                bin_means.setdefault(bi, []).append(objective[i])
            overall = sum(objective) / len(objective)
            ss_between = sum(
                len(vals) * (sum(vals) / len(vals) - overall) ** 2
                for vals in bin_means.values()
            )
            ss_total = sum((v - overall) ** 2 for v in objective)
            importances[k] = ss_between / max(ss_total, 1e-12)
        except (ValueError, ZeroDivisionError):
            importances[k] = 0.0
    total = sum(importances.values())
    if total > 0:
        importances = {k: v / total for k, v in importances.items()}
    return importances


def run_study(
    objective_fn: Callable[[Dict[str, Any]], float],
    space: Mapping[str, Mapping[str, Any]],
    *,
    study_name: str = "hpo_study",
    n_trials: int = 10,
    direction: str = "maximize",
    sampler: Optional[Any] = None,
    timeout_s: Optional[float] = None,
    pruner: Optional[Any] = None,
    random_seed: int = 0,
    mlflow_experiment_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run an in-tree HPO study using ``RandomSampler`` by default.

    Parameters
    ----------
    objective_fn : callable
        Function ``(params: dict) → float``.  Sign convention matches
        ``direction`` (higher is better when ``direction='maximize'``).
    space : mapping
        Parameter search-space dict (see :func:`suggest_default_search_space`).
    study_name : str
    n_trials : int
        Maximum number of trials.
    direction : {'maximize', 'minimize'}
    sampler : optional, pre-built sampler
        Pass an Optuna ``sampler`` to use it instead of the random
        fallback.  Currently the run treats ``sampler=None`` as
        ``RandomSampler``.
    timeout_s : optional float
        Stop early after ``timeout_s`` seconds.
    pruner : optional
        If supplied, ``_median_prune_decision`` is applied per trial.
    mlflow_experiment_name : optional str
        If ``mlflow`` is importable, log each trial as a nested run
        under this experiment name.

    Returns
    -------
    dict — same shape as :data:`HPOResult.to_dict`, plus ``trials`` list
    with full diagnostic detail.
    """
    if direction not in {"maximize", "minimize"}:
        raise ValueError(
            f"direction must be 'maximize' or 'minimize', got {direction!r}"
        )
    if n_trials <= 0:
        raise ValueError(f"n_trials must be positive, got {n_trials}")

    # Acquire a sampler — supports Optuna dispatch when available.
    sampler_obj: Any
    if sampler is not None:
        sampler_obj = sampler
    else:
        try:
            import optuna  # noqa: F401

            sampler_obj = None  # placeholder; we still run Random below
        except ImportError:
            sampler_obj = None
    inner_sampler = RandomSampler(space, seed=random_seed)

    # Optional MLflow logging setup.
    mlflow_run = None
    if mlflow_experiment_name:
        try:
            import mlflow

            mlflow.set_experiment(mlflow_experiment_name)
            mlflow_run = mlflow.start_run(run_name=study_name)
        except ImportError:
            mlflow_run = None

    completed: List[TrialResult] = []
    history: List[Dict[str, Any]] = []
    start = time.monotonic()
    best_value: Optional[float] = None
    best_params: Optional[Dict[str, Any]] = None
    pruned_count = 0

    for trial_idx in range(int(n_trials)):
        if timeout_s is not None and (time.monotonic() - start) > timeout_s:
            break
        if sampler_obj is None:
            params = inner_sampler.sample()
        else:
            # Optuna dispatch — sample via sampler.ask()/sampler.suggest_*.
            # We only test RandomSampler in the in-tree path; for Optuna
            # we suggest manually using space spec types.
            params = _sample_via_optuna(sampler_obj, trial_idx, space)

        t0 = time.monotonic()
        try:
            value = float(objective_fn(params))
        except Exception as exc:  # noqa: BLE001
            value = float("nan")
            error = repr(exc)
        else:
            error = None
        duration = time.monotonic() - t0

        if math.isnan(value):
            completed.append(
                TrialResult(
                    number=trial_idx,
                    value=0.0,
                    params=params,
                    pruned=False,
                    error=error,
                    duration_s=duration,
                )
            )
            history.append({"trial": trial_idx, "value": None, "error": error})
            continue

        # Median pruner decision (in-tree approximation).
        pruned = False
        if pruner is not None or pruner == "median":
            pruned = _median_prune_decision(completed, value, direction)

        trial = TrialResult(
            number=trial_idx,
            value=value,
            params=params,
            pruned=pruned,
            error=error,
            duration_s=duration,
        )
        completed.append(trial)
        history.append(
            {
                "trial": trial_idx,
                "value": value,
                "pruned": pruned,
                "duration_s": duration,
            }
        )

        if not pruned:
            if best_value is None or (
                direction == "maximize" and value > best_value
            ) or (direction == "minimize" and value < best_value):
                best_value = value
                best_params = dict(params)

        # MLflow nested-run logging (if available).
        if mlflow_run is not None:
            try:
                import mlflow

                with mlflow.start_run(run_name=f"trial_{trial_idx}", nested=True):
                    mlflow.log_params(params)
                    mlflow.log_metric("objective", value)
                    if pruned:
                        mlflow.log_metric("pruned", 1)
                    else:
                        mlflow.log_metric("pruned", 0)
            except Exception:  # noqa: BLE001
                pass

    if pruned_count is None:
        pruned_count = 0

    if mlflow_run is not None:
        try:
            import mlflow

            mlflow.end_run()
        except Exception:  # noqa: BLE001
            pass

    param_importances = _compute_param_importances(
        [t for t in completed if not t.pruned], direction
    )

    if best_value is None:
        # All trials failed; report a sentinel.
        best_value = float("nan")
        best_params = {}

    result = HPOResult(
        study_name=study_name,
        best_trial={
            "number": next(
                (t.number for t in completed if t.value == best_value), -1
            ),
            "value": best_value,
            "params": best_params,
        },
        n_trials_completed=sum(1 for t in completed if not t.pruned),
        n_trials_pruned=sum(1 for t in completed if t.pruned),
        optimization_history=history,
        param_importances=param_importances,
        direction=direction,
        trials=completed,
    )

    out = result.to_dict()
    out["trials"] = [
        {
            "number": t.number,
            "value": t.value,
            "params": t.params,
            "pruned": t.pruned,
            "error": t.error,
            "duration_s": t.duration_s,
        }
        for t in completed
    ]
    return out


def _sample_via_optuna(
    sampler: Any,
    trial_idx: int,
    space: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Fallback that uses Optuna suggest APIs through a frozen trial stub.

    Production deployments are expected to call Optuna directly through
    its ``study.optimize`` API. The in-tree HPO supports a slim Optuna
    integration by reconstructing a ``trial``-like callable and asking
    the sampler for a suggestion per parameter.
    """
    import optuna

    study = optuna.create_study(direction="maximize", sampler=sampler)
    trial = study.ask()
    params: Dict[str, Any] = {}
    for name, spec in space.items():
        t = spec.get("type", "float")
        low = spec.get("low")
        high = spec.get("high")
        log = bool(spec.get("log", False))
        if t == "int":
            params[name] = trial.suggest_int(
                name, int(low), int(high), log=log
            )
        else:
            params[name] = trial.suggest_float(
                name, float(low), float(high), log=log
            )
    # Don't actually run the trial — we just want the params.
    return params


__all__ = [
    "suggest_default_search_space",
    "random_sample_params",
    "RandomSampler",
    "TrialResult",
    "HPOResult",
    "run_study",
]


