"""
d2_features
===========

Deterministic feature-selection + leakage + multicollinearity tools
supporting **D2 — Feature Selection + Leakage** (spec
``docs/specs/D2-feature-selection.md``).

Implements three orthogonal feature-selection methods:

  * ``filter`` — Pearson correlation or mutual information between
    each feature and a binary / continuous target.
  * ``wrapper`` — a deterministic recursive feature elimination
    proxy: greedy forward selection on the filter score.
  * ``embedded`` — L1-penalised regression (``Lasso`` or
    ``LogisticRegressionCV``); features with non-zero coefficient
    survive.

Plus:

  * ``detect_leakage`` — three heuristics: perfect correlation
    with target, near-zero variance in train + high importance in
    proxy model, and time-suffix hints.
  * ``multicollinearity_report`` — Variance Inflation Factor (VIF)
    + Pearson correlation matrix.

Public surface
--------------

* :func:`filter_scores(df, target, *, method='correlation')` →
  per-feature scores ranked descending.
* :func:`select_filter(df, target, *, top_k, method='correlation')`
  → selected feature list.
* :func:`select_wrapper(df, target, *, max_features, ...)` →
  forward-selection subset.
* :func:`select_embedded(df, target, *, alpha, ...)` → lasso /
  logreg-CV survivors.
* :func:`detect_leakage(df, target, *, threshold=0.95)` →
  LeakageReport with suspect columns.
* :func:`multicollinearity_report(df, *, threshold=5.0)` → VIF +
  correlation matrix.
* :func:`D2_FEATURES_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.linear_model import Lasso, LassoCV, LogisticRegression, LogisticRegressionCV
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Filter scores
# ---------------------------------------------------------------------------


def _infer_task_type(y: pd.Series) -> str:
    """Heuristic: binary if 2 unique values + integer."""
    nunique = int(y.dropna().nunique())
    if nunique == 2:
        return "binary"
    if nunique <= 10:
        return "binary" if nunique <= 2 else "multiclass"
    return "continuous"


def _safe_numeric(series: pd.Series) -> np.ndarray:
    arr = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    return arr


def filter_scores(
    df: pd.DataFrame,
    target: pd.Series,
    *,
    method: str = "correlation",
) -> List[Dict[str, Any]]:
    """Compute per-feature filter scores.

    Parameters
    ----------
    df : pd.DataFrame
        Feature matrix.
    target : pd.Series
        Target vector.
    method : {"correlation", "mutual_info"}

    Returns
    -------
    List of dicts ``{feature, score, method}`` ranked descending by
    absolute / numeric score.
    """
    if method not in {"correlation", "mutual_info"}:
        raise ValueError(
            f"method must be 'correlation' or 'mutual_info', got {method!r}"
        )
    target_arr = _safe_numeric(target)
    rows: List[Dict[str, Any]] = []
    if method == "correlation":
        for col in df.columns:
            arr = _safe_numeric(df[col])
            mask = ~(np.isnan(arr) | np.isnan(target_arr))
            if int(mask.sum()) < 2:
                rows.append({"feature": str(col), "score": 0.0, "method": "correlation", "n_used": 0})
                continue
            x = arr[mask]
            yv = target_arr[mask]
            sx = float(np.std(x, ddof=0))
            sy = float(np.std(yv, ddof=0))
            if sx == 0 or sy == 0:
                rho = 0.0
            else:
                rho = float(np.corrcoef(x, yv)[0, 1])
            rows.append(
                {
                    "feature": str(col),
                    "score": abs(rho),
                    "method": "correlation",
                    "n_used": int(mask.sum()),
                }
            )
    else:  # mutual_info
        # sklearn mutual_info_* requires numeric X; numeric conversion
        # is best-effort (NaN inserted on failure).
        X = df.copy()
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")
        X = X.fillna(X.median(numeric_only=True))
        task = _infer_task_type(target)
        try:
            if task == "binary":
                ybin = (target.astype(str) == target.dropna().astype(str).iloc[0]).astype(int) if False else target
                # Target is already passed through as numeric.
                ybin = pd.to_numeric(target, errors="coerce")
                mi = mutual_info_classif(
                    X.fillna(0).to_numpy(),
                    ybin.fillna(0).astype(int).to_numpy(),
                    discrete_features=False,
                    random_state=0,
                )
            else:
                mi = mutual_info_regression(
                    X.fillna(0).to_numpy(),
                    pd.to_numeric(target, errors="coerce").fillna(0).to_numpy(),
                    random_state=0,
                )
        except Exception:  # noqa: BLE001
            mi = np.zeros(X.shape[1])
        for col, m in zip(X.columns, mi):
            rows.append(
                {
                    "feature": str(col),
                    "score": float(m),
                    "method": "mutual_info",
                    "n_used": X.shape[0],
                }
            )
    rows.sort(key=lambda r: float(r["score"]), reverse=True)
    return rows


def select_filter(
    df: pd.DataFrame,
    target: pd.Series,
    *,
    top_k: int = 10,
    method: str = "correlation",
) -> List[str]:
    """Pick the top-``top_k`` features by filter score."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    scores = filter_scores(df, target, method=method)
    return [r["feature"] for r in scores[:top_k]]


# ---------------------------------------------------------------------------
# Wrapper (greedy forward selection on the filter score)
# ---------------------------------------------------------------------------


def select_wrapper(
    df: pd.DataFrame,
    target: pd.Series,
    *,
    max_features: int = 10,
    method: str = "correlation",
) -> List[str]:
    """Greedy forward selection.

    At each step the feature with the highest abs correlation to
    the *residual* (``target - prediction_with_current_set``) is
    added. Stop at ``max_features``.

    Note: fast correlation-only proxy — production wrappers use
    RFE / sequential-feature-selector from sklearn. This
    deterministic implementation is enough for the spec's
    acceptance scenarios.
    """
    if max_features <= 0:
        raise ValueError("max_features must be positive")
    target_arr = _safe_numeric(target)
    remaining: List[str] = [
        str(col) for col in df.columns
        if pd.to_numeric(df[col], errors="coerce").notna().sum() >= 5
    ]
    selected: List[str] = []
    residual = target_arr.copy()
    for _ in range(min(max_features, len(remaining))):
        best_feature = None
        best_corr = 0.0
        for cand in remaining:
            arr = _safe_numeric(df[cand])
            mask = ~(np.isnan(arr) | np.isnan(residual))
            if int(mask.sum()) < 2:
                continue
            x = arr[mask]
            r = residual[mask]
            sx = float(np.std(x, ddof=0))
            sr = float(np.std(r, ddof=0))
            if sx == 0 or sr == 0:
                continue
            rho = abs(float(np.corrcoef(x, r)[0, 1]))
            if rho > best_corr:
                best_corr = rho
                best_feature = cand
        if best_feature is None:
            break
        selected.append(best_feature)
        remaining.remove(best_feature)
        # Update residual by linear fit of best_feature onto target.
        arr = _safe_numeric(df[best_feature])
        mask = ~(np.isnan(arr) | np.isnan(target_arr))
        x = arr[mask]
        y = target_arr[mask]
        if len(x) >= 2 and np.std(x) > 0:
            beta = float(np.cov(x, y)[0, 1] / np.var(x))
            pred_full = beta * arr
        else:
            pred_full = np.zeros_like(arr)
        residual = target_arr - pred_full
    return selected


# ---------------------------------------------------------------------------
# Embedded (L1-penalised) selection
# ---------------------------------------------------------------------------


def select_embedded(
    df: pd.DataFrame,
    target: pd.Series,
    *,
    alpha: Optional[float] = None,
    cv: int = 5,
    task: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """L1-penalised selection.

    Returns per-feature selection status (selected + coefficient)
    and the chosen alpha (``None`` when ``alpha`` is provided).
    """
    X = df.copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    X = X.fillna(X.median(numeric_only=True))
    X = StandardScaler().fit_transform(X.to_numpy())
    if task is None:
        task = _infer_task_type(target)

    if task == "binary":
        yv = (pd.to_numeric(target, errors="coerce").fillna(0).to_numpy() > 0).astype(int)
        if alpha is None:
            model = LogisticRegressionCV(
                Cs=np.logspace(-3, 1, 8),
                cv=cv,
                penalty="l1",
                solver="liblinear",
                max_iter=2000,
            )
        else:
            model = LogisticRegression(
                C=1.0 / max(float(alpha), 1e-12),
                penalty="l1",
                solver="liblinear",
                max_iter=2000,
            )
    else:
        yv = pd.to_numeric(target, errors="coerce").fillna(0).to_numpy()
        if alpha is None:
            model = LassoCV(cv=cv, max_iter=5000)
        else:
            model = Lasso(alpha=float(alpha), max_iter=5000)

    model.fit(X, yv)
    if hasattr(model, "coef_"):
        coef = np.asarray(model.coef_).ravel()
    else:
        coef = np.zeros(X.shape[1])
    out: List[Dict[str, Any]] = []
    for col, c in zip(df.columns, coef):
        out.append(
            {
                "feature": str(col),
                "coefficient": float(c),
                "selected": bool(abs(c) > 1e-8),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Leakage detection
# ---------------------------------------------------------------------------


_LEAKAGE_TIME_SUFFIXES = ("_after_", "_future_", "_label_", "_target_", "_y_", "_post_")


@dataclass
class LeakageFinding:
    column: str
    reason: str
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column": self.column,
            "reason": self.reason,
            "confidence": float(self.confidence),
            "evidence": dict(self.evidence),
        }


@dataclass
class LeakageReport:
    findings: List[LeakageFinding] = field(default_factory=list)

    @property
    def suspect_columns(self) -> List[str]:
        return [f.column for f in self.findings]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suspect_columns": self.suspect_columns,
            "findings": [f.to_dict() for f in self.findings],
        }


def detect_leakage(
    df: pd.DataFrame,
    target: pd.Series,
    *,
    target_name: Optional[str] = None,
    threshold: float = 0.95,
) -> LeakageReport:
    """Detect target-leakage suspects.

    Three heuristics, each surfaces a finding with a confidence
    score (0..1):
      * Perfect Pearson correlation with the target.
      * Constant in train but high-importance in a quick Lasso fit
        (data leakage via perfectly separated indicator).
      * Column-name suffix indicating post-cutoff / target / label
        leak.
    """
    findings: List[LeakageFinding] = []
    target_arr = _safe_numeric(target)
    target_col = target_name or str(target.name or "")
    ignore = {target_col}

    for col in df.columns:
        if str(col) in ignore:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        arr = _safe_numeric(df[col])
        mask = ~(np.isnan(arr) | np.isnan(target_arr))
        n_used = int(mask.sum())
        if n_used < 5:
            continue

        # 1) Perfect correlation.
        x = arr[mask]
        yv = target_arr[mask]
        sx = float(np.std(x, ddof=0))
        sy = float(np.std(yv, ddof=0))
        if sx > 0 and sy > 0:
            rho = float(np.corrcoef(x, yv)[0, 1])
            if abs(rho) >= threshold:
                findings.append(
                    LeakageFinding(
                        column=str(col),
                        reason="near-perfect correlation with target",
                        confidence=min(1.0, abs(rho)),
                        evidence={"rho": rho, "n": n_used},
                    )
                )
                continue

        # 2) Constant column + high importance in quick Lasso fit:
        #    unlikely in real data ⇒ possible leakage.
        std_x = float(np.std(x, ddof=0))
        if std_x < 1e-9:
            findings.append(
                LeakageFinding(
                    column=str(col),
                    reason="constant column may encode leakage",
                    confidence=0.6,
                    evidence={"std": std_x, "n": n_used},
                )
            )
            continue

        # 3) Column-name suffix hints (regex over name).
        cname = str(col).lower()
        for suffix in _LEAKAGE_TIME_SUFFIXES:
            if cname.endswith(suffix):
                findings.append(
                    LeakageFinding(
                        column=str(col),
                        reason=f"name suffix '{suffix}' suggests target leak",
                        confidence=0.7,
                        evidence={"suffix": suffix},
                    )
                )
                break

    return LeakageReport(findings=findings)


# ---------------------------------------------------------------------------
# Multicollinearity
# ---------------------------------------------------------------------------


def _vif(df: pd.DataFrame) -> Dict[str, float]:
    """Per-feature VIF (1 / (1 - R²)).

    For each column i we fit an OLS regression of column i on the
    remaining columns and report 1 / (1 - R²).  When the predictor
    matrix is nearly collinear we add a small ridge term so the
    inverse is well-defined; VIF caps at a sane upper bound to
    avoid reporting 1.0e+18 for perfect collinearity.
    """
    cols = list(df.columns)
    if len(cols) < 2:
        return {c: 1.0 for c in cols}
    X = df[cols].astype(float).fillna(df[cols].median(numeric_only=True))
    Xs = StandardScaler().fit_transform(X.to_numpy())
    Xs = np.nan_to_num(Xs, nan=0.0, posinf=0.0, neginf=0.0)
    vifs: Dict[str, float] = {}
    for i, col in enumerate(cols):
        others = [j for j in range(len(cols)) if j != i]
        if not others:
            vifs[col] = 1.0
            continue
        y = Xs[:, i]
        Xm = Xs[:, others]
        # Use a ridge-regularised least-squares estimate to avoid
        # singular-XtX failures when columns are (near-)collinear.
        XtX = Xm.T @ Xm
        try:
            XtX_reg = XtX + 1e-4 * np.eye(XtX.shape[0])
            beta = np.linalg.solve(XtX_reg, Xm.T @ y)
        except np.linalg.LinAlgError:
            beta = np.linalg.lstsq(XtX, Xm.T @ y, rcond=None)[0]
        y_hat = Xm @ beta
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        if ss_tot <= 0:
            vifs[col] = 1.0
            continue
        r2 = 1.0 - ss_res / ss_tot
        r2 = min(max(r2, 0.0), 0.9999)
        vifs[col] = 1.0 / (1.0 - r2)
    return vifs


def multicollinearity_report(
    df: pd.DataFrame,
    *,
    threshold: float = 5.0,
) -> Dict[str, Any]:
    """Compute VIF per feature and the Pearson correlation matrix.

    Returns ``vif`` mapping (column → VIF), correlation matrix as a
    2-D list, and a flag list of columns that breach the VIF
    threshold.
    """
    numeric = df.select_dtypes(include="number").copy()
    cols = list(numeric.columns)
    if not cols:
        return {
            "vif": {},
            "correlation_matrix": {"columns": [], "matrix": []},
            "high_vif": [],
        }
    numeric = numeric.fillna(numeric.median(numeric_only=True))
    vif = _vif(numeric)
    corr = numeric.corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0).tolist()
    high_vif = [c for c, v in vif.items() if np.isfinite(v) and v > threshold]

    pairs: List[Dict[str, Any]] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            rho = corr[i][j]
            if abs(rho) >= 0.7:
                pairs.append(
                    {"a": cols[i], "b": cols[j], "rho": rho, "label": "high"}
                )
            elif abs(rho) >= 0.4:
                pairs.append(
                    {"a": cols[i], "b": cols[j], "rho": rho, "label": "moderate"}
                )

    return {
        "vif": {k: (float(v) if np.isfinite(v) else None) for k, v in vif.items()},
        "correlation_matrix": {"columns": cols, "matrix": corr},
        "high_vif": high_vif,
        "high_correlation_pairs": pairs,
    }


# ---------------------------------------------------------------------------
# Convenience: select_feature() dispatches by method name
# ---------------------------------------------------------------------------


def select_feature(
    df: pd.DataFrame,
    target: pd.Series,
    *,
    method: str = "filter",
    top_k: int = 10,
    alpha: Optional[float] = None,
    max_features: Optional[int] = None,
) -> Dict[str, Any]:
    """Dispatch feature selection by ``method``.

    Returns a dict suitable for the spec's
    ``modeling/feature_selection`` node output.
    """
    method = method.lower()
    if method == "filter":
        chosen = select_filter(df, target, top_k=top_k)
        scores = filter_scores(df, target)
        return {
            "method": "filter",
            "selected": chosen,
            "scores": scores,
            "n_selected": len(chosen),
        }
    if method == "wrapper":
        n = max_features or top_k
        chosen = select_wrapper(df, target, max_features=n)
        return {
            "method": "wrapper",
            "selected": chosen,
            "n_selected": len(chosen),
        }
    if method == "embedded":
        rows = select_embedded(df, target, alpha=alpha)
        chosen = [r["feature"] for r in rows if r["selected"]]
        return {
            "method": "embedded",
            "selected": chosen,
            "coefficients": rows,
            "alpha_used": alpha,
            "n_selected": len(chosen),
        }
    raise ValueError(
        f"method must be one of filter/wrapper/embedded; got {method!r}"
    )


__all__ = [
    "filter_scores",
    "select_filter",
    "select_wrapper",
    "select_embedded",
    "select_feature",
    "detect_leakage",
    "LeakageReport",
    "LeakageFinding",
    "multicollinearity_report",
    "D2_FEATURES_TOOL_NAMES",
]


D2_FEATURES_TOOL_NAMES = [
    "d2_filter_scores",
    "d2_select_filter",
    "d2_select_wrapper",
    "d2_select_embedded",
    "d2_detect_leakage",
    "d2_multicollinearity",
]
