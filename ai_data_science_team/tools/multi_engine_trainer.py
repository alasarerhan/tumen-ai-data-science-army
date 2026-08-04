from __future__ import annotations

"""
e1_multi_engine_trainer
======================

Deterministic model-training tools for **E1 — Multi-Engine Trainer**
(spec from ``docs/specs/E1-multi-engine-trainer.md``).

Provides a unified adapter for sklearn / XGBoost / LightGBM models that
G4 (batch scoring), F2 (champion-challenger), and the workflow runtime
can use without depending on H2O.

The module exposes:

* :func:`candidates_for_task` — return a sensible default candidate
  list per ``task_type`` ("classification" / "regression") and engine.
* :func:`build_pipeline` — produce an sklearn ``Pipeline`` that bundles
  a light imputer/scaler with the candidate model.
* :func:`cross_validate_candidates` — run cross-validation across all
  candidates with ``cv`` settings and return per-candidate metrics.
"""

from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401
from sklearn.compose import ColumnTransformer  # noqa: E402, F401
from sklearn.impute import SimpleImputer  # noqa: E402, F401
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score  # noqa: E402, F401
from sklearn.pipeline import Pipeline  # noqa: E402, F401
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Candidates registry
# ---------------------------------------------------------------------------


CANDIDATES_BY_TASK: Dict[str, Dict[str, str]] = {
    "classification": {
        "sklearn": "LogisticRegression",
        "xgboost": "XGBClassifier",
        "lightgbm": "LGBMClassifier",
    },
    "regression": {
        "sklearn": "Ridge",
        "xgboost": "XGBRegressor",
        "lightgbm": "LGBMRegressor",
    },
}


SENSIBLE_CANDIDATES: Dict[str, List[str]] = {
    "classification": ["sklearn", "xgboost", "lightgbm"],
    "regression": ["sklearn", "xgboost", "lightgbm"],
}


# Scoring metric per task.
SCORING_BY_TASK: Dict[str, str] = {
    "classification": "roc_auc",
    "regression": "neg_mean_squared_error",
}


def candidates_for_task(task_type: str, engine: str) -> str:
    """Return the class name for the candidate model of ``engine``.

    Parameters
    ----------
    task_type : str
        ``"classification"`` or ``"regression"``.
    engine : str
        ``"sklearn"``, ``"xgboost"`` or ``"lightgbm"``.

    Returns
    -------
    str — the sklearn-xgboost-or-lightgbm class name.

    Raises
    ------
    ValueError for unknown task_type or engine.
    """
    if task_type not in CANDIDATES_BY_TASK:
        raise ValueError(f"Unknown task_type '{task_type}'. Known: {sorted(CANDIDATES_BY_TASK)}")
    if engine not in CANDIDATES_BY_TASK[task_type]:
        raise ValueError(
            f"Unknown engine '{engine}' for task '{task_type}'. "
            f"Known: {sorted(CANDIDATES_BY_TASK[task_type])}"
        )
    return CANDIDATES_BY_TASK[task_type][engine]


# ---------------------------------------------------------------------------
# Pipeline construction
# ---------------------------------------------------------------------------


def _detect_feature_types(
    df: pd.DataFrame,
) -> Tuple[List[str], List[str]]:
    cat, num = [], []
    for col in df.columns:
        s = df[col]
        if s.dtype.kind in "biufc":
            num.append(col)
        else:
            cat.append(col)
    return cat, num


def _build_preprocessor(
    cat_cols: Sequence[str],
    num_cols: Sequence[str],
) -> ColumnTransformer:
    """Return a ColumnTransformer that handles missing + scale + OHE."""
    transformers = []
    if num_cols:
        num_pipe = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        transformers.append(("num", num_pipe, list(num_cols)))
    if cat_cols:
        cat_pipe = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
        transformers.append(("cat", cat_pipe, list(cat_cols)))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def _instantiate_estimator(
    task_type: str,
    engine: str,
    engine_params: Optional[Mapping[str, Any]],
) -> Any:
    """Instantiate the model class with sensible defaults + ``engine_params``."""
    cls_name = candidates_for_task(task_type, engine)
    params: Dict[str, Any] = dict(engine_params or {})
    # Default n_estimators for gradient boosters.
    if engine in {"xgboost", "lightgbm"} and "n_estimators" not in params:
        params.setdefault("n_estimators", 200)
    if engine in {"xgboost"} and params.get("use_label_encoder") is None:
        # xgboost ≥ 1.5 ignores use_label_encoder; leave default.
        pass
    if engine == "xgboost":
        try:
            import xgboost as xgb  # noqa: E402, F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "xgboost is not installed; install `xgboost` to use engine='xgboost'"
            ) from exc
        cls = getattr(xgb, cls_name)
    elif engine == "lightgbm":
        try:
            import lightgbm as lgb  # noqa: E402, F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "lightgbm is not installed; install `lightgbm` to use engine='lightgbm'"
            ) from exc
        cls = getattr(lgb, cls_name)
    elif engine == "sklearn":
        from sklearn import ensemble, linear_model  # noqa: E402, F401

        if cls_name == "LogisticRegression":
            return linear_model.LogisticRegression(max_iter=1000, **params)
        if cls_name == "Ridge":
            return linear_model.Ridge(**params)
        if cls_name == "RandomForestClassifier":
            return ensemble.RandomForestClassifier(**params)
        if cls_name == "RandomForestRegressor":
            return ensemble.RandomForestRegressor(**params)
        raise ValueError(f"sklearn does not provide a default class for '{cls_name}'")
    else:  # pragma: no cover
        raise ValueError(f"Unsupported engine '{engine}'")
    return cls(**params)


def build_pipeline(
    X: pd.DataFrame,
    task_type: str,
    engine: str,
    engine_params: Optional[Mapping[str, Any]] = None,
) -> Pipeline:
    """Build a sklearn Pipeline imputer+scaler+OHE → estimator.

    The returned pipeline ``fit(X, y)`` produces a deterministic binary
    classification/regression model whose ``predict`` and
    ``predict_proba`` (where supported) are immediately callable.
    """
    cat_cols, num_cols = _detect_feature_types(X)
    preprocessor = _build_preprocessor(cat_cols, num_cols)
    estimator = _instantiate_estimator(task_type, engine, engine_params)
    return Pipeline(steps=[("prep", preprocessor), ("model", estimator)])


# ---------------------------------------------------------------------------
# Cross-validation across candidates
# ---------------------------------------------------------------------------


@dataclass
class CVResult:
    engine: str
    candidate_name: str
    metrics: Dict[str, float]  # scoring metric -> mean + std
    n_splits: int
    n_samples: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "candidate_name": self.candidate_name,
            "metrics": self.metrics,
            "n_splits": self.n_splits,
            "n_samples": self.n_samples,
            "error": self.error,
        }


def _make_cv(task_type: str, cv_cfg: Mapping[str, Any]):
    n = int(cv_cfg.get("n_splits", 5))
    rs = int(cv_cfg.get("random_state", 42))
    shuf = bool(cv_cfg.get("shuffle", True))
    strategy = cv_cfg.get("strategy", "stratified_kfold")
    if task_type == "classification" and strategy == "stratified_kfold":
        return StratifiedKFold(n_splits=n, shuffle=shuf, random_state=rs)
    return KFold(n_splits=n, shuffle=shuf, random_state=rs)


def cross_validate_candidates(
    X: pd.DataFrame,
    y: pd.Series,
    task_type: str,
    candidates: Optional[Sequence[str]] = None,
    engine_params: Optional[Mapping[str, Any]] = None,
    cv: Optional[Mapping[str, Any]] = None,
    **engine_overrides: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Run cross-validation for each engine in ``candidates``.

    Parameters
    ----------
    X : pd.DataFrame
    y : pd.Series
    task_type : str
    candidates : sequence of str, optional
        Engines to evaluate (default: ``SENSIBLE_CANDIDATES[task]``).
    engine_params : mapping, optional
        Per-task default parameters; per-engine overrides can be
        supplied via the ``engine_overrides`` kwargs.
    cv : mapping, optional
        Cross-validation settings (``strategy``, ``n_splits``,
        ``shuffle``, ``random_state``).
    engine_overrides : mapping of per-engine parameter dicts, e.g.
        ``xgboost={"n_estimators": 500, "max_depth": 6}``.

    Returns
    -------
    dict with key ``results`` (list of :class:`CVResult` dicts) and
    ``best_engine`` (engine with highest scoring metric mean — sklearn
    negative RMSE is converted to positive RMSE for ranking).
    """
    if task_type not in CANDIDATES_BY_TASK:
        raise ValueError(f"Unknown task_type '{task_type}'. Known: {sorted(CANDIDATES_BY_TASK)}")
    candidates = list(candidates or SENSIBLE_CANDIDATES[task_type])
    cv_obj = _make_cv(task_type, cv or {})
    scoring = SCORING_BY_TASK[task_type]

    results: List[CVResult] = []
    best_engine: Optional[str] = None
    best_score: float = float("-inf")

    for engine in candidates:
        candidate_name = candidates_for_task(task_type, engine)
        # Engine-specific params override task-default params.
        per_engine_params: Dict[str, Any] = {
            **dict(engine_params or {}),
            **dict(engine_overrides.get(engine, {})),
        }
        try:
            pipe = build_pipeline(X, task_type, engine, per_engine_params)
            scores = cross_val_score(pipe, X, y, cv=cv_obj, scoring=scoring, error_score="raise")
            mean = float(np.mean(scores))
            std = float(np.std(scores))
            results.append(
                CVResult(
                    engine=engine,
                    candidate_name=candidate_name,
                    metrics={
                        "mean": mean,
                        "std": std,
                        "scoring": scoring,
                        "is_higher_better": scoring != "neg_mean_squared_error",
                    },
                    n_splits=cv_obj.get_n_splits(),
                    n_samples=int(len(y)),
                )
            )
            ranking = mean if scoring != "neg_mean_squared_error" else -mean
            if ranking > best_score:
                best_score = ranking
                best_engine = engine
        except Exception as exc:  # noqa: BLE001
            results.append(
                CVResult(
                    engine=engine,
                    candidate_name=candidate_name,
                    metrics={
                        "mean": 0.0,
                        "std": 0.0,
                        "scoring": scoring,
                        "is_higher_better": scoring != "neg_mean_squared_error",
                    },
                    n_splits=cv_obj.get_n_splits(),
                    n_samples=int(len(y)),
                    error=repr(exc),
                )
            )

    # If nothing succeeded, fall back to the first candidate.
    if best_engine is None and candidates:
        best_engine = candidates[0]
    return {
        "results": [r.to_dict() for r in results],
        "best_engine": best_engine,
        "best_score": best_score,
        "scoring": scoring,
        "n_splits": cv_obj.get_n_splits(),
    }


def select_best_model(
    cv_output: Mapping[str, Any],
) -> Dict[str, Any]:
    """Pick the highest-scoring engine from a ``cross_validate_candidates`` output."""
    return {
        "best_engine": cv_output.get("best_engine"),
        "best_score": cv_output.get("best_score"),
        "n_evaluated": len(cv_output.get("results", [])),
    }


__all__ = [
    "candidates_for_task",
    "build_pipeline",
    "cross_validate_candidates",
    "select_best_model",
]
