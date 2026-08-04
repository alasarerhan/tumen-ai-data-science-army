from __future__ import annotations

"""f3_fairness. Deterministic fairness + bias audit tools.

Implements the F3 spec.  Fairlearn is referenced for
``MetricFrame``/``demographic_parity_difference`` but not bundled;
the tool ships a pure-Python implementation that matches the
spec's I/O contract end-to-end.
"""

from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Optional, Sequence  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401

FOUR_FIFTHS = 0.8


# ---------------------------------------------------------------------------
# Per-group metrics
# ---------------------------------------------------------------------------


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den else float("nan")


def per_group_metrics(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    sensitive: Sequence,
) -> pd.DataFrame:
    """Per-group base rates + selection/TPR/FPR."""
    df = pd.DataFrame(
        {
            "y_true": np.asarray(y_true).astype(int),
            "y_pred": np.asarray(y_pred).astype(int),
            "group": list(sensitive),
        },
    )
    rows = []
    for g, sub in df.groupby("group"):
        n = len(sub)
        n_pos = int((sub["y_true"] == 1).sum())
        n_pred_pos = int((sub["y_pred"] == 1).sum())
        n_pred_pos_given_pos = int(((sub["y_true"] == 1) & (sub["y_pred"] == 1)).sum())
        n_pred_pos_given_neg = int(((sub["y_true"] == 0) & (sub["y_pred"] == 1)).sum())
        tpr = _safe_div(n_pred_pos_given_pos, n_pos)
        fpr = _safe_div(n_pred_pos_given_neg, max(n - n_pos, 1))
        rows.append(
            {
                "group": str(g),
                "n": n,
                "positive_rate": _safe_div(n_pos, n),
                "selection_rate": _safe_div(n_pred_pos, n),
                "tpr": tpr,
                "fpr": fpr,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


def demographic_parity_difference(group_df: pd.DataFrame) -> float:
    """Max selection_rate − min selection_rate across groups."""
    if "selection_rate" not in group_df.columns or group_df.empty:
        return float("nan")
    return float(group_df["selection_rate"].max() - group_df["selection_rate"].min())


def demographic_parity_ratio(group_df: pd.DataFrame) -> float:
    """Min / max selection_rate.  Range 0-1, 1 = perfect parity."""
    if group_df.empty:
        return float("nan")
    mn = group_df["selection_rate"].min()
    mx = group_df["selection_rate"].max()
    if mx == 0:
        return float("nan")
    return float(mn / mx)


def equalized_odds_difference(group_df: pd.DataFrame) -> float:
    """Max TPR − min TPR (FPR contribution is symmetrical; we
    use the TPR side of the spec for the deterministic core)."""
    if "tpr" not in group_df.columns or group_df.empty:
        return float("nan")
    return float(group_df["tpr"].max() - group_df["tpr"].min())


# ---------------------------------------------------------------------------
# 80% rule + flagging
# ---------------------------------------------------------------------------


def violates_four_fifths(
    group_df: pd.DataFrame,
    *,
    threshold: float = FOUR_FIFTHS,
) -> Dict[str, bool]:
    """Return per-group violation of the 80% rule (ratio < threshold)."""
    rates = {}
    if group_df.empty or "selection_rate" not in group_df.columns:
        return rates
    mx = group_df["selection_rate"].max()
    if mx == 0:
        return {str(r.group): False for r in group_df.itertuples()}
    for row in group_df.itertuples():
        rates[str(row.group)] = (row.selection_rate / mx) < threshold
    return rates


# ---------------------------------------------------------------------------
# Mitigation simulation (threshold-only)
# ---------------------------------------------------------------------------


def simulate_threshold_mitigation(
    y_true: Sequence[int],
    y_pred_proba: Sequence[float],
    sensitive: Sequence,
    target_rate: Optional[float] = None,
) -> pd.DataFrame:
    """Simulate equalized-odds post-processing by picking per-group
    thresholds that equalise the selection rate to ``target_rate``
    (default: unmitigated average)."""
    df = pd.DataFrame(
        {
            "y_true": np.asarray(y_true).astype(int),
            "y_proba": np.asarray(y_pred_proba, dtype=float),
            "group": list(sensitive),
        },
    )
    if df.empty:
        return pd.DataFrame(
            columns=[
                "group",
                "threshold",
                "selection_rate",
            ]
        )
    if target_rate is None:
        target_rate = float(df["y_proba"].mean())
    rows = []
    for g, sub in df.groupby("group"):
        sorted_sub = sub.sort_values("y_proba", ascending=False)
        k = int(round(target_rate * len(sorted_sub)))
        k = max(0, min(k, len(sorted_sub)))
        thresh = float(sorted_sub["y_proba"].iloc[k - 1]) if k > 0 else 1.0
        new_selection = float(sub["y_proba"].ge(thresh).mean())
        rows.append(
            {
                "group": str(g),
                "threshold": thresh,
                "selection_rate": new_selection,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


@dataclass
class FairnessReport:
    group_metrics: pd.DataFrame
    dp_difference: float
    dp_ratio: float
    eod: float
    four_fifths_violations: Dict[str, bool]
    mitigated: Optional[pd.DataFrame] = None
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_metrics": self.group_metrics.to_dict(orient="records"),
            "dp_difference": self.dp_difference,
            "dp_ratio": self.dp_ratio,
            "eod": self.eod,
            "four_fifths_violations": self.four_fifths_violations,
            "mitigated": (
                self.mitigated.to_dict(orient="records") if self.mitigated is not None else None
            ),
            "recommendations": list(self.recommendations),
        }


def audit_fairness(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    sensitive: Sequence,
    *,
    sensitive_column: Optional[str] = None,
    y_proba: Optional[Sequence[float]] = None,
    threshold: float = FOUR_FIFTHS,
) -> FairnessReport:
    """Run the full F3 audit on a single protected attribute.

    ``sensitive_column`` is a documentation string used for the
    report; the ``sensitive`` sequence carries the per-row group
    membership.
    """
    gm = per_group_metrics(y_true, y_pred, sensitive)
    dpd = demographic_parity_difference(gm)
    dpr = demographic_parity_ratio(gm)
    eod = equalized_odds_difference(gm)
    violations = violates_four_fifths(gm, threshold=threshold)

    mitigated: Optional[pd.DataFrame] = None
    if y_proba is not None:
        mitigated = simulate_threshold_mitigation(y_true, y_proba, sensitive)

    recs = _make_recommendations(
        dpd=dpd,
        dpr=dpr,
        eod=eod,
        violations=violations,
        sensitive_column=sensitive_column,
    )
    return FairnessReport(
        group_metrics=gm,
        dp_difference=dpd,
        dp_ratio=dpr,
        eod=eod,
        four_fifths_violations=violations,
        mitigated=mitigated,
        recommendations=recs,
    )


def _make_recommendations(
    *,
    dpd: float,
    dpr: float,
    eod: float,
    violations: Dict[str, bool],
    sensitive_column: Optional[str],
) -> List[str]:
    out = []
    if any(violations.values()):
        group = ", ".join(g for g, v in violations.items() if v)
        out.append(
            f"80% rule violated by group(s): {group}. "
            "Consider reweighing or threshold optimisation."
        )
    if not (np.isnan(dpd)) and dpd > 0.1:
        out.append("Demographic parity difference > 0.1; review training-data balance.")
    if not (np.isnan(eod)) and eod > 0.1:
        out.append("Equalised-odds gap > 0.1; consider equalised-odds post-processing.")
    if not (np.isnan(dpr)) and dpr < 0.8:
        out.append("Selection-rate ratio < 0.8 (4/5 rule); rebalance or mitigate.")
    if not out:
        out.append(
            f"No fairness issues detected for sensitive attribute"
            f"{' ' + sensitive_column if sensitive_column else ''}."
        )
    return out


__all__ = [
    "FOUR_FIFTHS",
    "per_group_metrics",
    "demographic_parity_difference",
    "demographic_parity_ratio",
    "equalized_odds_difference",
    "violates_four_fifths",
    "simulate_threshold_mitigation",
    "FairnessReport",
    "audit_fairness",
]
