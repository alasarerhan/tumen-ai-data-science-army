from __future__ import annotations

"""
g1_drift
========

Deterministic drift-detection tools for **G1 — Otomatik Drift Hesabı**
(spec from ``docs/specs/G1-auto-drift.md``).

Implements:

* :func:`psi` — Population Stability Index between baseline and current
  numerical samples (decision thresholds: < 0.10 none, 0.10-0.25
  moderate, ≥ 0.25 significant).
* :func:`ks2` — two-sample Kolmogorov–Smirnov statistic.
* :func:`feature_drift_report` — per-feature drift across a feature
  frame; returns a structured JSON with ``signals`` (per-column
  status + PSI/KS), ``overall_drift`` and ``feature_heatmap``.
* :func:`performance_drift` — change in a primary metric between two
  windows; returns ``delta``, ``delta_pct``, ``threshold_breached``.
* :func:`drift_signal_payload` — combine feature + performance into a
  single payload consumable by G2 retrain-policy agent.
"""

import math  # noqa: E402, F401
from typing import Any, Dict, List, Optional, Sequence  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Numerical drift metrics
# ---------------------------------------------------------------------------


def _histogram_edges(values: np.ndarray, n_bins: int = 10) -> np.ndarray:
    """Build histogram edges for a numerical sample, robust to duplicates."""
    vmin, vmax = float(np.min(values)), float(np.max(values))
    if vmin == vmax:
        eps = max(abs(vmin), 1.0) * 1e-3
        return np.linspace(vmin - eps, vmax + eps, n_bins + 1)
    return np.linspace(vmin, vmax, n_bins + 1)


def psi(
    baseline: Sequence[float] | np.ndarray,
    current: Sequence[float] | np.ndarray,
    n_bins: int = 10,
    eps: float = 1e-6,
) -> float:
    """Population Stability Index between two numerical samples.

    Both samples are binned into ``n_bins`` histogram bins sharing the
    same edges (from the baseline sample). Returns 0.0 when the two
    distributions are identical.
    """
    base = np.asarray(baseline, dtype=float).ravel()
    cur = np.asarray(current, dtype=float).ravel()
    if base.size == 0 or cur.size == 0:
        return 0.0
    edges = _histogram_edges(base, n_bins=n_bins)
    p_base = np.histogram(base, bins=edges)[0].astype(float)
    p_cur = np.histogram(cur, bins=edges)[0].astype(float)
    p_base = (p_base + eps) / (p_base.sum() + eps * len(p_base))
    p_cur = (p_cur + eps) / (p_cur.sum() + eps * len(p_cur))
    return float(np.sum((p_cur - p_base) * np.log(p_cur / p_base)))


def ks2(
    baseline: Sequence[float] | np.ndarray,
    current: Sequence[float] | np.ndarray,
) -> float:
    """Two-sample Kolmogorov–Smirnov statistic (no p-value)."""
    base = np.asarray(baseline, dtype=float).ravel()
    cur = np.asarray(current, dtype=float).ravel()
    if base.size == 0 or cur.size == 0:
        return 0.0
    a = np.sort(base)
    b = np.sort(cur)
    # Empirical CDFs over the union of the two sample points.
    union = np.sort(np.concatenate([a, b]))
    cdf_a = np.searchsorted(a, union, side="right") / a.size
    cdf_b = np.searchsorted(b, union, side="right") / b.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


# ---------------------------------------------------------------------------
# Drift severity buckets
# ---------------------------------------------------------------------------


def _psi_severity(value: float) -> str:
    if value >= 0.25:
        return "significant"
    if value >= 0.10:
        return "moderate"
    if value > 0.0:
        return "minor"
    return "none"


def _ks_severity(value: float) -> str:
    # Two-sample KS critical values for n > 100 are around 0.135 at 5 %
    if value >= 0.20:
        return "significant"
    if value >= 0.10:
        return "moderate"
    if value > 0.0:
        return "minor"
    return "none"


# ---------------------------------------------------------------------------
# Feature-drift report
# ---------------------------------------------------------------------------


def feature_drift_report(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    *,
    n_bins: int = 10,
    columns: Optional[Sequence[str]] = None,
    include_numeric: bool = True,
) -> Dict[str, Any]:
    """Compute per-feature drift between two DataFrames of the same schema.

    Numeric columns are checked with PSI + KS2; categorical columns are
    checked with PSI applied to value-counts.

    Returns
    -------
    dict with keys ``signals`` (list of per-column dicts), ``overall_drift``
    (signed float: max severity score) and ``feature_heatmap`` (list of
    dicts ready for ``<HeatmapChart>``).
    """
    if columns is None:
        columns = sorted(set(baseline_df.columns) & set(current_df.columns))
    signals: List[Dict[str, Any]] = []
    heatmap: List[Dict[str, Any]] = []
    severity_score = {"none": 0, "minor": 1, "moderate": 2, "significant": 3}

    base_cols = list(baseline_df.columns)
    cur_cols = list(current_df.columns)
    if set(base_cols) != set(cur_cols):
        missing_in_current = set(base_cols) - set(cur_cols)
        missing_in_baseline = set(cur_cols) - set(base_cols)
        if missing_in_current or missing_in_baseline:
            signals.append(
                {
                    "column": "__schema__",
                    "kind": "schema",
                    "status": "warning",
                    "severity": "moderate",
                    "missing_in_current": sorted(missing_in_current),
                    "missing_in_baseline": sorted(missing_in_baseline),
                }
            )

    max_score = 0
    for col in columns:
        if col not in baseline_df.columns or col not in current_df.columns:
            continue
        base_series = baseline_df[col]
        cur_series = current_df[col]
        is_numeric = (
            include_numeric
            and pd.api.types.is_numeric_dtype(base_series)
            and pd.api.types.is_numeric_dtype(cur_series)
        )
        if is_numeric and base_series.notna().sum() >= 5 and cur_series.notna().sum() >= 5:
            base_vals = base_series.dropna().to_numpy()
            cur_vals = cur_series.dropna().to_numpy()
            psi_val = psi(base_vals, cur_vals, n_bins=n_bins)
            ks_val = ks2(base_vals, cur_vals)
            psi_sev = _psi_severity(psi_val)
            ks_sev = _ks_severity(ks_val)
            combined_sev = max(severity_score[psi_sev], severity_score[ks_sev])
            combined_label = [k for k, v in severity_score.items() if v == combined_sev][0]
            signals.append(
                {
                    "column": col,
                    "kind": "numeric",
                    "psi": float(psi_val),
                    "ks2": float(ks_val),
                    "psi_severity": psi_sev,
                    "ks_severity": ks_sev,
                    "severity": combined_label,
                    "status": ("drift" if combined_label != "none" else "ok"),
                }
            )
            heatmap.append({"column": col, "metric": "psi", "value": float(psi_val)})
            heatmap.append({"column": col, "metric": "ks2", "value": float(ks_val)})
            max_score = max(max_score, combined_sev)
        else:
            # Categorical or low-coverage numeric → categorical PSI.
            base_counts = base_series.astype(str).value_counts(normalize=True).to_dict()
            cur_counts = cur_series.astype(str).value_counts(normalize=True).to_dict()
            keys = sorted(set(base_counts) | set(cur_counts))
            cat_psi = 0.0
            eps = 1e-6
            for k in keys:
                p = base_counts.get(k, eps)
                q = cur_counts.get(k, eps)
                cat_psi += (q - p) * math.log(q / p)
            cat_sev = _psi_severity(cat_psi)
            cat_score = severity_score[cat_sev]
            signals.append(
                {
                    "column": col,
                    "kind": "categorical",
                    "psi": float(cat_psi),
                    "severity": cat_sev,
                    "status": "drift" if cat_sev != "none" else "ok",
                }
            )
            heatmap.append({"column": col, "metric": "psi", "value": float(cat_psi)})
            max_score = max(max_score, cat_score)

    return {
        "signals": signals,
        "overall_drift": [k for k, v in severity_score.items() if v == max_score][0],
        "feature_heatmap": heatmap,
    }


# ---------------------------------------------------------------------------
# Performance drift
# ---------------------------------------------------------------------------


def performance_drift(
    baseline_metric: float,
    current_metric: float,
    *,
    lower_is_better: bool = False,
    relative_threshold: float = 0.05,
    absolute_threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Compare two scalar metric values and report breach status.

    Returns
    -------
    dict with keys ``baseline``, ``current``, ``delta``,
    ``delta_pct``, ``threshold_breached``, ``direction``.
    """
    delta = float(current_metric - baseline_metric)
    denom = baseline_metric if baseline_metric not in (0, 0.0) else 1.0
    delta_pct = float(delta / denom)

    if lower_is_better:
        improved = delta < 0
    else:
        improved = delta > 0

    if absolute_threshold is not None:
        breached = abs(delta) >= abs(absolute_threshold)
    else:
        breached = (
            (delta_pct <= -abs(relative_threshold))
            if not lower_is_better
            else (delta_pct >= abs(relative_threshold))
        )

    return {
        "baseline": baseline_metric,
        "current": current_metric,
        "delta": delta,
        "delta_pct": delta_pct,
        "improved": improved,
        "threshold_breached": breached,
        "lower_is_better": lower_is_better,
        "relative_threshold": relative_threshold,
        "absolute_threshold": absolute_threshold,
    }


# ---------------------------------------------------------------------------
# Combined drift signal payload (consumable by G2)
# ---------------------------------------------------------------------------


def drift_signal_payload(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    *,
    feature_report: Optional[Dict[str, Any]] = None,
    baseline_metric: Optional[float] = None,
    current_metric: Optional[float] = None,
    metric_name: str = "roc_auc",
    lower_is_better: bool = False,
    relative_threshold: float = 0.05,
    n_bins: int = 10,
) -> Dict[str, Any]:
    """Combine feature-drift and performance-drift into a single payload."""
    if feature_report is None:
        feature_report = feature_drift_report(baseline_df, current_df, n_bins=n_bins)
    perf_drift: Optional[Dict[str, Any]] = None
    if baseline_metric is not None and current_metric is not None:
        perf_drift = performance_drift(
            baseline_metric,
            current_metric,
            lower_is_better=lower_is_better,
            relative_threshold=relative_threshold,
        )
    feature_drift_trigger = feature_report["overall_drift"] in {
        "moderate",
        "significant",
    }
    perf_trigger = bool(perf_drift and perf_drift["threshold_breached"])
    return {
        "feature_report": feature_report,
        "performance": perf_drift,
        "metric_name": metric_name,
        "feature_drift_trigger": feature_drift_trigger,
        "performance_trigger": perf_trigger,
        "should_retrain": feature_drift_trigger or perf_trigger,
    }


__all__ = [
    "psi",
    "ks2",
    "feature_drift_report",
    "performance_drift",
    "drift_signal_payload",
]
