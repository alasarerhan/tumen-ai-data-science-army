"""j6_responsible_ai. Deterministic Responsible-AI dashboard tools.
Implements J6 — combine fairness metrics (F3), explainability
(SHAP-like feature contributions), and error slicing into a
single dashboard payload. Flags violations and emits mitigation
suggestions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass
class FairnessSlice:
    """Per-group fairness numbers (selection rate, tpr, fpr)."""
    group: str
    n: int
    selection_rate: float
    true_positive_rate: float
    false_positive_rate: float


@dataclass
class FairnessReport:
    protected_attribute: str
    slices: List[FairnessSlice]
    demographic_parity_diff: float
    equalized_odds_diff: float
    threshold: float
    violations: List[str]


@dataclass
class FeatureContribution:
    feature: str
    mean_abs_shap: float
    global_importance_rank: int


@dataclass
class ExplainabilityReport:
    method: str  # "shap_tree" | "shap_kernel" | "permutation"
    contributions: List[FeatureContribution]
    top_k: int


@dataclass
class ErrorSlice:
    slice_expr: str
    n: int
    error_rate: float
    baseline_error_rate: float
    lift: float  # (slice_error - baseline) / baseline


@dataclass
class ResponsibleAIDashboard:
    model_id: str
    fairness: Optional[FairnessReport]
    explainability: Optional[ExplainabilityReport]
    error_slices: List[ErrorSlice]
    violations: List[str]
    mitigations: List[str]


# ----- Fairness ------------------------------------------------------------

def compute_fairness(
    *,
    protected_attribute: str,
    group_labels: Sequence[str],
    y_true: Sequence[int],
    y_pred: Sequence[int],
    threshold: float = 0.10,
) -> FairnessReport:
    if len(y_true) != len(y_pred) or len(y_true) != len(group_labels):
        raise ValueError("y_true, y_pred, group_labels must have same length")
    slices: List[FairnessSlice] = []
    by_group: Dict[str, Tuple[List[int], List[int]]] = {}
    for g, t, p in zip(group_labels, y_true, y_pred):
        by_group.setdefault(str(g), ([], []))[0].append(int(t))
        by_group.setdefault(str(g), ([], []))[1].append(int(p))
    for g, (ts, ps) in by_group.items():
        n = len(ts)
        sel = sum(ps) / n if n else float("nan")
        pos = [i for i, t in enumerate(ts) if t == 1]
        tp = sum(1 for i in pos if ps[i] == 1)
        fn = sum(1 for i in pos if ps[i] == 0)
        fp = sum(1 for i, t in enumerate(ts) if t == 0 and ps[i] == 1)
        tn = sum(1 for i, t in enumerate(ts) if t == 0 and ps[i] == 0)
        tpr = tp / (tp + fn) if (tp + fn) else float("nan")
        fpr = fp / (fp + tn) if (fp + tn) else float("nan")
        slices.append(FairnessSlice(
            group=g, n=n, selection_rate=sel,
            true_positive_rate=tpr, false_positive_rate=fpr,
        ))
    sel_rates = [s.selection_rate for s in slices if not math.isnan(s.selection_rate)]
    dp_diff = (max(sel_rates) - min(sel_rates)) if len(sel_rates) >= 2 else 0.0
    tprs = [s.true_positive_rate for s in slices if not math.isnan(s.true_positive_rate)]
    fprs = [s.false_positive_rate for s in slices if not math.isnan(s.false_positive_rate)]
    eo_tpr = (max(tprs) - min(tprs)) if len(tprs) >= 2 else 0.0
    eo_fpr = (max(fprs) - min(fprs)) if len(fprs) >= 2 else 0.0
    eo_diff = max(eo_tpr, eo_fpr)
    violations: List[str] = []
    if dp_diff > threshold:
        violations.append(
            f"demographic_parity_diff {dp_diff:.3f} > {threshold:.3f}"
        )
    if eo_diff > threshold:
        violations.append(
            f"equalized_odds_diff {eo_diff:.3f} > {threshold:.3f}"
        )
    return FairnessReport(
        protected_attribute=protected_attribute,
        slices=slices,
        demographic_parity_diff=dp_diff,
        equalized_odds_diff=eo_diff,
        threshold=threshold,
        violations=violations,
    )


# ----- Explainability ------------------------------------------------------

def compute_explainability(
    *,
    feature_names: Sequence[str],
    shap_abs_means: Sequence[float],
    method: str = "shap_tree",
    top_k: int = 10,
) -> ExplainabilityReport:
    if len(feature_names) != len(shap_abs_means):
        raise ValueError("feature_names and shap_abs_means must align")
    pairs = sorted(
        zip(feature_names, shap_abs_means),
        key=lambda x: x[1], reverse=True,
    )
    contribs = [
        FeatureContribution(
            feature=name,
            mean_abs_shap=float(val),
            global_importance_rank=rank,
        )
        for rank, (name, val) in enumerate(pairs[:top_k], start=1)
    ]
    return ExplainabilityReport(
        method=method, contributions=contribs, top_k=top_k,
    )


# ----- Error slicing -------------------------------------------------------

def discover_error_slices(
    *,
    y_true: Sequence[int],
    y_pred: Sequence[int],
    feature_values: Mapping[str, Sequence[Any]],
    baseline_error_rate: Optional[float] = None,
    min_slice_n: int = 30,
    top_k: int = 10,
) -> List[ErrorSlice]:
    """Naive slice discovery: walk each feature's value histogram
    and pick the values whose error rate is materially above
    baseline. Returns up to top_k slices."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must align")
    n = len(y_true)
    if baseline_error_rate is None:
        errors = [int(t != p) for t, p in zip(y_true, y_pred)]
        baseline_error_rate = sum(errors) / n if n else 0.0
    out: List[ErrorSlice] = []
    for feat, values in feature_values.items():
        if len(values) != n:
            continue
        by_val: Dict[Any, List[int]] = {}
        for v, t, p in zip(values, y_true, y_pred):
            by_val.setdefault(v, []).append(int(t != p))
        for v, errs in by_val.items():
            if len(errs) < min_slice_n:
                continue
            rate = sum(errs) / len(errs)
            lift = (rate - baseline_error_rate) / baseline_error_rate \
                if baseline_error_rate > 0 else 0.0
            if lift > 0:
                out.append(ErrorSlice(
                    slice_expr=f"{feat}={v!r}",
                    n=len(errs),
                    error_rate=rate,
                    baseline_error_rate=baseline_error_rate,
                    lift=lift,
                ))
    out.sort(key=lambda s: s.lift, reverse=True)
    return out[:top_k]


# ----- Mitigations ---------------------------------------------------------

def suggest_mitigations(
    fairness: Optional[FairnessReport],
    error_slices: Sequence[ErrorSlice],
) -> List[str]:
    out: List[str] = []
    if fairness is not None and fairness.violations:
        out.append(
            "Apply reweighing or reject-option classification on the "
            f"protected attribute '{fairness.protected_attribute}'."
        )
        out.append(
            "Collect more representative training data for "
            "underperforming groups."
        )
    if error_slices:
        worst = error_slices[0]
        out.append(
            f"Investigate slice '{worst.slice_expr}' "
            f"(error_rate={worst.error_rate:.3f}, lift={worst.lift:.2f})."
        )
        out.append("Consider sample-weighting or feature-engineering for "
                    "the worst-performing slice.")
    if not out:
        out.append("No mitigations required.")
    return out


# ----- Dashboard -----------------------------------------------------------

def build_dashboard(
    *,
    model_id: str,
    fairness: Optional[FairnessReport] = None,
    explainability: Optional[ExplainabilityReport] = None,
    error_slices: Optional[Sequence[ErrorSlice]] = None,
) -> ResponsibleAIDashboard:
    errs = list(error_slices or [])
    violations: List[str] = []
    if fairness is not None:
        violations.extend(fairness.violations)
    mitigations = suggest_mitigations(fairness, errs)
    if violations:
        mitigations.insert(0, "Model does not currently pass the responsible-AI gate.")
    return ResponsibleAIDashboard(
        model_id=model_id,
        fairness=fairness,
        explainability=explainability,
        error_slices=errs,
        violations=violations,
        mitigations=mitigations,
    )


def dashboard_payload(d: ResponsibleAIDashboard) -> Dict[str, Any]:
    """Convert dashboard to UI-ready dict (JSON-safe)."""
    return {
        "model_id": d.model_id,
        "fairness": (
            None if d.fairness is None else
            {
                "protected_attribute": d.fairness.protected_attribute,
                "demographic_parity_diff": d.fairness.demographic_parity_diff,
                "equalized_odds_diff": d.fairness.equalized_odds_diff,
                "threshold": d.fairness.threshold,
                "slices": [
                    {
                        "group": s.group, "n": s.n,
                        "selection_rate": s.selection_rate,
                        "true_positive_rate": s.true_positive_rate,
                        "false_positive_rate": s.false_positive_rate,
                    } for s in d.fairness.slices
                ],
                "violations": d.fairness.violations,
            }
        ),
        "explainability": (
            None if d.explainability is None else
            {
                "method": d.explainability.method,
                "top_k": d.explainability.top_k,
                "contributions": [
                    {
                        "feature": c.feature,
                        "mean_abs_shap": c.mean_abs_shap,
                        "rank": c.global_importance_rank,
                    } for c in d.explainability.contributions
                ],
            }
        ),
        "error_slices": [
            {
                "slice_expr": e.slice_expr, "n": e.n,
                "error_rate": e.error_rate,
                "baseline_error_rate": e.baseline_error_rate,
                "lift": e.lift,
            } for e in d.error_slices
        ],
        "violations": d.violations,
        "mitigations": d.mitigations,
    }


J6_RESPONSIBLE_AI_TOOL_NAMES: List[str] = [
    "j6_compute_fairness",
    "j6_compute_explainability",
    "j6_discover_error_slices",
    "j6_suggest_mitigations",
    "j6_build_dashboard",
    "j6_dashboard_payload",
]
