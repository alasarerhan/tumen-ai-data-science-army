"""d4_balance. Deterministic imbalanced-data tools. Implements D4
— class distribution analysis + imbalance detection + strategy
selection (smote / undersampling / class_weight / threshold_tuning)
+ per-strategy impact estimation + PR-AUC recommendation.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np


VALID_STRATEGIES = {"smote", "undersampling", "class_weight", "threshold_tuning", "none"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


# ----- Class distribution --------------------------------------------------

@dataclass
class ClassDistribution:
    counts: Dict[Any, int]
    n: int
    n_classes: int
    majority_count: int
    minority_count: int
    imbalance_ratio: float


def class_distribution(y: Sequence[Any]) -> ClassDistribution:
    counts: Dict[Any, int] = {}
    for label in y:
        counts[label] = counts.get(label, 0) + 1
    n = len(y)
    n_classes = len(counts)
    if n_classes == 0 or n == 0:
        return ClassDistribution(
            counts=counts, n=n, n_classes=n_classes,
            majority_count=0, minority_count=0,
            imbalance_ratio=1.0,
        )
    sorted_counts = sorted(counts.values(), reverse=True)
    majority = sorted_counts[0]
    minority = sorted_counts[-1]
    ir = majority / minority if minority > 0 else float("inf")
    return ClassDistribution(
        counts=counts, n=n, n_classes=n_classes,
        majority_count=majority, minority_count=minority,
        imbalance_ratio=ir,
    )


def is_imbalanced(
    dist: ClassDistribution, *,
    threshold: float = 1.5,
    severe_threshold: float = 10.0,
) -> Dict[str, Any]:
    """Return a verdict + suggested severity."""
    if dist.imbalance_ratio >= severe_threshold:
        severity = "severe"
    elif dist.imbalance_ratio >= threshold:
        severity = "moderate"
    else:
        severity = "balanced"
    return {
        "is_imbalanced": severity in ("moderate", "severe"),
        "severity": severity,
        "imbalance_ratio": dist.imbalance_ratio,
        "threshold": threshold,
        "severe_threshold": severe_threshold,
    }


# ----- Strategy selection --------------------------------------------------

def select_strategy(
    dist: ClassDistribution,
    *,
    dataset_size: Optional[int] = None,
    prefers_interpretability: bool = False,
    has_synthetic_capability: bool = True,
) -> Dict[str, Any]:
    """Heuristic strategy selector.

    * severe imbalance (>=10x): prefer SMOTE if available, else
      class_weight.
    * moderate imbalance (1.5x..10x): class_weight is cheapest.
    * balanced: no rebalancing needed.
    * small dataset (<5000): undersampling is risky → prefer
      class_weight or threshold tuning.
    * interpretability preference boosts class_weight / threshold.
    """
    verdict = is_imbalanced(dist)
    ir = dist.imbalance_ratio
    n = dataset_size if dataset_size is not None else dist.n
    candidates: List[Tuple[str, float]] = []  # (strategy, score)
    if verdict["severity"] == "balanced":
        return {
            "primary": "none",
            "rationale": "Classes are roughly balanced.",
            "alternatives": [],
            "verdict": verdict,
        }
    if ir >= 10.0:
        if has_synthetic_capability:
            candidates.append(("smote", 1.0))
        candidates.append(("class_weight", 0.7))
        candidates.append(("threshold_tuning", 0.6))
    elif ir >= 1.5:
        candidates.append(("class_weight", 0.9))
        candidates.append(("threshold_tuning", 0.7))
        candidates.append(("smote", 0.5))
    if n < 5000:
        # down-weight undersampling for tiny datasets
        candidates.append(("undersampling", 0.4))
    else:
        candidates.append(("undersampling", 0.6))
    if prefers_interpretability:
        # boost cheap interpretable options
        adjusted: List[Tuple[str, float]] = []
        for s, score in candidates:
            if s in ("class_weight", "threshold_tuning"):
                adjusted.append((s, score + 0.2))
            else:
                adjusted.append((s, score - 0.1))
        candidates = adjusted
    candidates.sort(key=lambda kv: kv[1], reverse=True)
    primary = candidates[0][0]
    alternatives = [s for s, _ in candidates[1:]]
    return {
        "primary": primary,
        "alternatives": alternatives,
        "rationale": _build_rationale(primary, verdict, n),
        "verdict": verdict,
    }


def _build_rationale(
    primary: str, verdict: Mapping[str, Any], n: int,
) -> str:
    ir = verdict["imbalance_ratio"]
    if primary == "smote":
        return (
            f"Severe imbalance (IR={ir:.1f}); SMOTE will synthetically "
            "expand the minority class without losing majority data."
        )
    if primary == "class_weight":
        return (
            f"{verdict['severity'].title()} imbalance (IR={ir:.1f}); "
            "class weighting is the cheapest intervention and preserves "
            "the original sample distribution."
        )
    if primary == "undersampling":
        return (
            f"Imbalance (IR={ir:.1f}) with n={n}; undersampling trims the "
            "majority class. Less ideal when dataset is small."
        )
    if primary == "threshold_tuning":
        return (
            f"Imbalance (IR={ir:.1f}); threshold tuning rebalances "
            "decision boundary without resampling."
        )
    return "No rebalancing needed."


# ----- Per-strategy impact estimation -------------------------------------

def estimate_strategy_impact(
    dist: ClassDistribution,
    strategy: str,
) -> Dict[str, Any]:
    """Project how the strategy will reshape the distribution.

    * smote: minority grows to majority size (synthetic).
    * undersampling: majority trims to minority size.
    * class_weight: weights inversely proportional to freq
      (informational; no resampling).
    * threshold_tuning: no sample change.
    """
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"strategy must be one of {sorted(VALID_STRATEGIES)}"
        )
    if dist.n == 0 or dist.n_classes == 0:
        return {
            "strategy": strategy,
            "before": {"n": 0, "imbalance_ratio": 1.0},
            "after": {"n": 0, "imbalance_ratio": 1.0},
            "effective": False,
        }
    before = {
        "n": dist.n,
        "imbalance_ratio": dist.imbalance_ratio,
    }
    if strategy == "smote":
        target = dist.majority_count
        added = target - dist.minority_count
        new_n = dist.n + added
        after = {"n": new_n, "imbalance_ratio": 1.0}
        effective = True
    elif strategy == "undersampling":
        kept_majority = dist.minority_count
        new_n = kept_majority * dist.n_classes
        after = {"n": new_n, "imbalance_ratio": 1.0}
        effective = True
    elif strategy == "class_weight":
        weights = {
            cls: dist.n / (dist.n_classes * count)
            for cls, count in dist.counts.items()
        }
        after = {
            "n": dist.n,
            "imbalance_ratio": dist.imbalance_ratio,
            "weights": weights,
        }
        effective = False
    elif strategy == "threshold_tuning":
        after = {"n": dist.n, "imbalance_ratio": dist.imbalance_ratio}
        effective = False
    else:  # "none"
        after = {"n": dist.n, "imbalance_ratio": dist.imbalance_ratio}
        effective = False
    return {
        "strategy": strategy,
        "before": before,
        "after": after,
        "effective": effective,
    }


# ----- PR-AUC recommendation ----------------------------------------------

@dataclass
class PRAUCRecommendation:
    primary_metric: str
    rationale: str
    secondary_metrics: List[str]


def recommend_metrics(
    dist: ClassDistribution,
) -> PRAUCRecommendation:
    """For imbalanced classification, recommend PR-AUC primary
    with ROC-AUC and F1 secondary; for balanced, accuracy is fine."""
    verdict = is_imbalanced(dist)
    if verdict["is_imbalanced"]:
        return PRAUCRecommendation(
            primary_metric="pr_auc",
            rationale=(
                "Class imbalance detected; PR-AUC is more sensitive "
                "to minority-class performance than ROC-AUC."
            ),
            secondary_metrics=["roc_auc", "f1", "recall_at_k"],
        )
    return PRAUCRecommendation(
        primary_metric="accuracy",
        rationale="Classes are roughly balanced; accuracy is informative.",
        secondary_metrics=["f1", "roc_auc"],
    )


# ----- Sampling helpers ----------------------------------------------------

def undersample_indices(
    y: Sequence[Any],
    *,
    target_ratio: float = 1.0,
    random_state: Optional[int] = None,
) -> List[int]:
    """Return indices after majority-class undersampling so that
    majority:minority == target_ratio (or close to it)."""
    if not y:
        return []
    counts: Dict[Any, List[int]] = {}
    for i, label in enumerate(y):
        counts.setdefault(label, []).append(i)
    if len(counts) < 2:
        return list(range(len(y)))
    sorted_classes = sorted(counts, key=lambda k: len(counts[k]), reverse=True)
    majority_cls = sorted_classes[0]
    minority_size = min(len(v) for v in counts.values())
    target_majority = max(1, int(round(minority_size * target_ratio)))
    rng = np.random.default_rng(random_state)
    majority_indices = counts[majority_cls]
    if target_majority >= len(majority_indices):
        keep_majority = list(majority_indices)
    else:
        keep_majority = list(
            rng.choice(majority_indices, size=target_majority, replace=False)
        )
    out = list(keep_majority)
    for cls in sorted_classes[1:]:
        out.extend(counts[cls])
    out.sort()
    return out


def class_weight(y: Sequence[Any]) -> Dict[Any, float]:
    """Inverse-frequency weights, normalised to sum to n_classes."""
    dist = class_distribution(y)
    if dist.n == 0 or dist.n_classes == 0:
        return {}
    return {
        cls: dist.n / (dist.n_classes * count)
        for cls, count in dist.counts.items()
    }


# ----- Apply (resampled row indices) ---------------------------------------

@dataclass
class SamplingReport:
    strategy: str
    original_n: int
    resampled_n: int
    original_distribution: Dict[Any, int]
    resampled_distribution: Dict[Any, int]
    kept_indices: List[int]
    rationale: str


def apply_strategy(
    y: Sequence[Any],
    strategy: str,
    *,
    target_ratio: float = 1.0,
    random_state: Optional[int] = 42,
) -> SamplingReport:
    if strategy not in VALID_STRATEGIES:
        raise ValueError(
            f"strategy must be one of {sorted(VALID_STRATEGIES)}"
        )
    dist = class_distribution(y)
    if strategy == "undersampling":
        idx = undersample_indices(
            y, target_ratio=target_ratio, random_state=random_state,
        )
        kept_y = [y[i] for i in idx]
        return SamplingReport(
            strategy=strategy,
            original_n=dist.n,
            resampled_n=len(idx),
            original_distribution=dict(dist.counts),
            resampled_distribution=class_distribution(kept_y).counts,
            kept_indices=idx,
            rationale="Majority class trimmed to match target ratio.",
        )
    # other strategies keep all indices
    return SamplingReport(
        strategy=strategy,
        original_n=dist.n,
        resampled_n=dist.n,
        original_distribution=dict(dist.counts),
        resampled_distribution=dict(dist.counts),
        kept_indices=list(range(dist.n)),
        rationale=(
            "No resampling; impact is at training time (sample "
            "weights or decision threshold)."
        ),
    )


# ----- Dashboard payload ---------------------------------------------------

def balance_payload(
    dist: ClassDistribution,
    *,
    dataset_size: Optional[int] = None,
    prefers_interpretability: bool = False,
    has_synthetic_capability: bool = True,
) -> Dict[str, Any]:
    strategy = select_strategy(
        dist,
        dataset_size=dataset_size,
        prefers_interpretability=prefers_interpretability,
        has_synthetic_capability=has_synthetic_capability,
    )
    impact = estimate_strategy_impact(dist, strategy["primary"])
    metrics = recommend_metrics(dist)
    return {
        "distribution": {
            "counts": dist.counts,
            "n": dist.n,
            "n_classes": dist.n_classes,
            "imbalance_ratio": dist.imbalance_ratio,
        },
        "verdict": strategy["verdict"],
        "selected_strategy": strategy["primary"],
        "alternatives": strategy["alternatives"],
        "rationale": strategy["rationale"],
        "impact": impact,
        "recommended_metrics": {
            "primary": metrics.primary_metric,
            "rationale": metrics.rationale,
            "secondary": metrics.secondary_metrics,
        },
    }


D4_BALANCE_TOOL_NAMES: List[str] = [
    "d4_class_distribution",
    "d4_is_imbalanced",
    "d4_select_strategy",
    "d4_estimate_strategy_impact",
    "d4_recommend_metrics",
    "d4_undersample_indices",
    "d4_class_weight",
    "d4_apply_strategy",
    "d4_balance_payload",
]
