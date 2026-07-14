"""j1_investigation. Deterministic autonomous-investigation tools.
Implements J1 — multi-step investigation pipeline triggered by a
KPI change signal. Four phases: detect → isolate → quantify →
narrate. Each phase produces a structured artifact, and the final
narrative is a templated, evidence-linked summary suitable for
publishing to the insights feed.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


@dataclass
class KPISignal:
    signal_id: str
    kpi_name: str
    baseline_value: float
    current_value: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionResult:
    detected: bool
    abs_delta: float
    relative_delta: float
    z_score: float
    threshold: float


@dataclass
class IsolationResult:
    """Which dimension(s) drove the change."""
    candidate_dimensions: List[str]
    dimension_scores: Dict[str, float]
    primary_dimension: Optional[str]


@dataclass
class QuantificationResult:
    """How much each group contributes to the delta."""
    contributors: List[Dict[str, Any]]
    total_delta: float


@dataclass
class Narrative:
    title: str
    summary: str
    evidence_links: List[Dict[str, Any]]
    recommended_actions: List[str]


@dataclass
class Investigation:
    investigation_id: str
    signal: KPISignal
    detection: DetectionResult
    isolation: IsolationResult
    quantification: QuantificationResult
    narrative: Narrative
    started_at: float
    completed_at: float


# ----- Phase 1: detect -----------------------------------------------------

def detect_change(
    *,
    baseline_value: float,
    current_value: float,
    historical_std: float = 1.0,
    z_threshold: float = 2.0,
    min_relative_delta: float = 0.05,
) -> DetectionResult:
    abs_delta = current_value - baseline_value
    rel_delta = abs_delta / baseline_value if baseline_value else float("nan")
    z = abs_delta / historical_std if historical_std > 0 else float("nan")
    triggered = (abs(z) >= z_threshold) and (abs(rel_delta) >= min_relative_delta)
    return DetectionResult(
        detected=triggered,
        abs_delta=abs_delta,
        relative_delta=rel_delta,
        z_score=z,
        threshold=z_threshold,
    )


# ----- Phase 2: isolate ----------------------------------------------------

def isolate_dimension(
    *,
    baseline_by_dim: Mapping[str, Mapping[str, float]],
    current_by_dim: Mapping[str, Mapping[str, float]],
    top_k: int = 5,
) -> IsolationResult:
    """baseline_by_dim: {dimension: {value: kpi_value}}
    current_by_dim: same shape."""
    scores: Dict[str, float] = {}
    for dim in set(baseline_by_dim) & set(current_by_dim):
        per_value_deltas = []
        for v in set(baseline_by_dim[dim]) & set(current_by_dim[dim]):
            try:
                b = float(baseline_by_dim[dim][v])
                c = float(current_by_dim[dim][v])
                per_value_deltas.append(abs(c - b))
            except (TypeError, ValueError):
                continue
        if per_value_deltas:
            scores[dim] = sum(per_value_deltas) / len(per_value_deltas)
    ranked = sorted(scores, key=scores.get, reverse=True)
    primary = ranked[0] if ranked else None
    return IsolationResult(
        candidate_dimensions=ranked[:top_k],
        dimension_scores=scores,
        primary_dimension=primary,
    )


# ----- Phase 3: quantify ---------------------------------------------------

def quantify_contributors(
    *,
    baseline_total: float,
    current_total: float,
    contributions: Sequence[Mapping[str, Any]],
) -> QuantificationResult:
    """contributions: [{'name': 'X', 'baseline': 100, 'current': 80},
    ...]. Returns contribution share + magnitude."""
    rows: List[Dict[str, Any]] = []
    total_delta = current_total - baseline_total
    for c in contributions:
        b = float(c.get("baseline", 0))
        cur = float(c.get("current", 0))
        delta = cur - b
        share = (delta / total_delta) if total_delta != 0 else 0.0
        rows.append({
            "name": str(c.get("name", "")),
            "baseline": b,
            "current": cur,
            "delta": delta,
            "contribution_share": share,
        })
    rows.sort(key=lambda r: abs(r["contribution_share"]), reverse=True)
    return QuantificationResult(
        contributors=rows, total_delta=total_delta,
    )


# ----- Phase 4: narrate ----------------------------------------------------

def narrate(
    *,
    signal: KPISignal,
    detection: DetectionResult,
    isolation: IsolationResult,
    quantification: QuantificationResult,
    actions: Optional[Sequence[str]] = None,
) -> Narrative:
    direction = "up" if detection.abs_delta > 0 else "down"
    title = (
        f"{signal.kpi_name} {direction} "
        f"{abs(detection.relative_delta) * 100:.1f}%"
    )
    primary = isolation.primary_dimension or "no clear dimension"
    worst = (
        quantification.contributors[0]
        if quantification.contributors else None
    )
    summary_parts = [
        f"KPI '{signal.kpi_name}' moved "
        f"{direction} by {abs(detection.relative_delta) * 100:.1f}% "
        f"(z={detection.z_score:.2f}).",
        f"Primary driver: {primary}.",
    ]
    if worst is not None:
        summary_parts.append(
            f"Worst contributor: {worst['name']} "
            f"(delta={worst['delta']:.2f}, share={worst['contribution_share']*100:.1f}%)."
        )
    summary = " ".join(summary_parts)
    evidence = [
        {"type": "kpi_snapshot",
         "ref": {"baseline": signal.baseline_value,
                 "current": signal.current_value}},
        {"type": "isolation",
         "ref": isolation.dimension_scores},
        {"type": "contributors",
         "ref": quantification.contributors},
    ]
    return Narrative(
        title=title,
        summary=summary,
        evidence_links=evidence,
        recommended_actions=list(actions or []),
    )


# ----- Orchestrator --------------------------------------------------------

def investigate(
    *,
    kpi_name: str,
    baseline_value: float,
    current_value: float,
    baseline_by_dim: Optional[Mapping[str, Mapping[str, float]]] = None,
    current_by_dim: Optional[Mapping[str, Mapping[str, float]]] = None,
    contributions: Optional[Sequence[Mapping[str, Any]]] = None,
    historical_std: float = 1.0,
    z_threshold: float = 2.0,
    min_relative_delta: float = 0.05,
    actions: Optional[Sequence[str]] = None,
) -> Investigation:
    signal = KPISignal(
        signal_id=_new_id(),
        kpi_name=kpi_name,
        baseline_value=baseline_value,
        current_value=current_value,
        timestamp=_now(),
    )
    det = detect_change(
        baseline_value=baseline_value,
        current_value=current_value,
        historical_std=historical_std,
        z_threshold=z_threshold,
        min_relative_delta=min_relative_delta,
    )
    iso = isolate_dimension(
        baseline_by_dim=baseline_by_dim or {},
        current_by_dim=current_by_dim or {},
    )
    quant = quantify_contributors(
        baseline_total=baseline_value,
        current_total=current_value,
        contributions=contributions or [],
    )
    narr = narrate(
        signal=signal, detection=det,
        isolation=iso, quantification=quant, actions=actions,
    )
    return Investigation(
        investigation_id=_new_id(),
        signal=signal,
        detection=det,
        isolation=iso,
        quantification=quant,
        narrative=narr,
        started_at=signal.timestamp,
        completed_at=_now(),
    )


J1_INVESTIGATION_TOOL_NAMES: List[str] = [
    "j1_detect_change",
    "j1_isolate_dimension",
    "j1_quantify_contributors",
    "j1_narrate",
    "j1_investigate",
]
