from __future__ import annotations

"""
c4_rootcause
===========

Deterministic root-cause analysis tools supporting **C4 — Root
Cause Analysis** (spec ``docs/specs/C4-root-cause-analysis.md``).

Companion to C3 (KPI).  When a KPI changes, the deterministic
core here computes:
  * Waterfall decomposition of the metric change by a
    ``dimension`` column (segments → contribution to Δmetric).
  * Top-N segment ranking by absolute contribution.
  * Hierarchical drill-down to a finer-grain dimension
    (spec says "her boyuta tıklayıp alt kırılımları drill-down").
  * LLM narrative stub: deterministic template → the agent
    layer replaces placeholders with the actual story.

Public surface
--------------

* :func:`waterfall(df, *, metric_col, dimension, baseline_window,
  current_window, agg='mean', top_n=10)` → WaterfallResult.
* :func:`drill_down(df, *, metric_col, dimension, parent_value,
  child_dimension, baseline_window, current_window)` →
  DrillDownResult.
* :func:`render_narrative(result, *, kpi_name)` → str (template
  narrative for the agent layer to enrich).
"""

import math  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Mapping  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _filter_window(df: pd.DataFrame, *, dimension: str, value: Any) -> pd.DataFrame:
    if value is None:
        return df
    if dimension not in df.columns:
        return df.iloc[0:0]
    return df[df[dimension] == value]


def _aggregate(df: pd.DataFrame, *, metric_col: str, agg: str) -> float:
    if metric_col not in df.columns or df.empty:
        return float("nan")
    series = pd.to_numeric(df[metric_col], errors="coerce").dropna()
    if series.empty:
        return float("nan")
    if agg == "mean":
        return float(series.mean())
    if agg == "median":
        return float(series.median())
    if agg == "sum":
        return float(series.sum())
    if agg == "count":
        return float(series.count())
    raise ValueError(f"unsupported agg: {agg!r}")


# ---------------------------------------------------------------------------
# Waterfall decomposition
# ---------------------------------------------------------------------------


@dataclass
class WaterfallSegment:
    segment: Any
    baseline_value: float
    current_value: float
    delta: float
    contribution_share: float
    sample_size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment": self.segment,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "delta": self.delta,
            "contribution_share": float(self.contribution_share),
            "sample_size": int(self.sample_size),
        }


@dataclass
class WaterfallResult:
    metric: str
    dimension: str
    aggregation: str
    baseline_total: float
    current_total: float
    total_delta: float
    segments: List[WaterfallSegment] = field(default_factory=list)
    top_drivers: List[Dict[str, Any]] = field(default_factory=list)
    top_drains: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "dimension": self.dimension,
            "aggregation": self.aggregation,
            "baseline_total": float(self.baseline_total),
            "current_total": float(self.current_total),
            "total_delta": float(self.total_delta),
            "segments": [s.to_dict() for s in self.segments],
            "top_drivers": list(self.top_drivers),
            "top_drains": list(self.top_drains),
        }


def waterfall(
    df: pd.DataFrame,
    *,
    metric_col: str,
    dimension: str,
    baseline_window: Mapping[str, Any],
    current_window: Mapping[str, Any],
    agg: str = "mean",
    top_n: int = 10,
) -> WaterfallResult:
    """Decompose a metric change by a dimension.

    The ``baseline_window`` and ``current_window`` are filters
    passed to ``pandas.DataFrame.query()`` so callers can express
    the comparison window as a normal query string (e.g. date
    ranges, environment flags, etc.).
    """
    if metric_col not in df.columns:
        raise ValueError(f"metric_col {metric_col!r} not in DataFrame")
    if dimension not in df.columns:
        raise ValueError(f"dimension {dimension!r} not in DataFrame")
    base_q = str(baseline_window.get("query", "")).strip()
    cur_q = str(current_window.get("query", "")).strip()
    base_df = df.query(base_q) if base_q else df.copy()
    cur_df = df.query(cur_q) if cur_q else df.copy()

    base_total = _aggregate(base_df, metric_col=metric_col, agg=agg)
    cur_total = _aggregate(cur_df, metric_col=metric_col, agg=agg)
    total_delta = cur_total - base_total

    # Decompose across the dimension — mean of metric within each
    # segment, weighted by sample size when ``agg='mean'`` so the
    # contribution shares add up to 1.0 regardless of segment
    # sizes.
    segments: List[WaterfallSegment] = []
    n_cur_total = max(int(len(cur_df)), 1)
    for seg, grp in cur_df.groupby(dimension, dropna=False):
        cur_val = _aggregate(grp, metric_col=metric_col, agg=agg)
        base_grp = _filter_window(base_df, dimension=dimension, value=seg)
        base_val = _aggregate(base_grp, metric_col=metric_col, agg=agg)
        # Weighted-mean delta: scales the segment's mean shift by
        # the share of rows it represents, so the sum equals
        # total_delta.
        if agg in ("mean", "median"):
            weight = float(len(grp)) / float(n_cur_total)
            delta = (cur_val - base_val) * weight
        else:
            # sum / count: weight is implicit in the deltas.
            delta = cur_val - base_val
        segments.append(
            WaterfallSegment(
                segment=seg,
                baseline_value=base_val,
                current_value=cur_val,
                delta=delta,
                contribution_share=0.0,  # filled below
                sample_size=int(len(grp)),
            )
        )
    # Contribution share — segment delta divided by total delta so
    # the sum equals 1.0 (when total_delta != 0).
    if total_delta != 0 and not math.isnan(total_delta):
        for s in segments:
            s.contribution_share = s.delta / total_delta
    # Top drivers / drains.
    sorted_pos = sorted(
        [s for s in segments if s.delta > 0],
        key=lambda x: x.delta,
        reverse=True,
    )[:top_n]
    sorted_neg = sorted(
        [s for s in segments if s.delta < 0],
        key=lambda x: x.delta,
    )[:top_n]
    return WaterfallResult(
        metric=metric_col,
        dimension=dimension,
        aggregation=agg,
        baseline_total=base_total,
        current_total=cur_total,
        total_delta=total_delta,
        segments=segments,
        top_drivers=[s.to_dict() for s in sorted_pos],
        top_drains=[s.to_dict() for s in sorted_neg],
    )


# ---------------------------------------------------------------------------
# Drill-down to a child dimension
# ---------------------------------------------------------------------------


@dataclass
class DrillSlice:
    label: str
    parent: Any
    child: Any
    baseline_value: float
    current_value: float
    delta: float
    sample_size: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "parent": self.parent,
            "child": self.child,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "delta": float(self.delta),
            "sample_size": int(self.sample_size),
        }


@dataclass
class DrillDownResult:
    parent_dimension: str
    child_dimension: str
    parent_value: Any
    slices: List[DrillSlice] = field(default_factory=list)
    top_drivers: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_dimension": self.parent_dimension,
            "child_dimension": self.child_dimension,
            "parent_value": self.parent_value,
            "slices": [s.to_dict() for s in self.slices],
            "top_drivers": list(self.top_drivers),
        }


def drill_down(
    df: pd.DataFrame,
    *,
    metric_col: str,
    dimension: str,
    parent_value: Any,
    child_dimension: str,
    baseline_window: Mapping[str, Any],
    current_window: Mapping[str, Any],
    agg: str = "mean",
    top_n: int = 10,
) -> DrillDownResult:
    """Drill from ``parent_value`` into the next ``child_dimension``.

    Returns per-child slices with baseline/current aggregates and
    delta.  Top-N by absolute delta.
    """
    if dimension not in df.columns or child_dimension not in df.columns:
        raise ValueError("both dimension and child_dimension must be in DataFrame")
    base_q = str(baseline_window.get("query", "")).strip()
    cur_q = str(current_window.get("query", "")).strip()
    base_df = df.query(base_q) if base_q else df.copy()
    cur_df = df.query(cur_q) if cur_q else df.copy()

    base_parents = _filter_window(base_df, dimension=dimension, value=parent_value)
    cur_parents = _filter_window(cur_df, dimension=dimension, value=parent_value)

    slices: List[DrillSlice] = []
    for child_val, grp in cur_parents.groupby(child_dimension, dropna=False):
        cur_val = _aggregate(grp, metric_col=metric_col, agg=agg)
        base_child = _filter_window(base_parents, dimension=child_dimension, value=child_val)
        base_val = _aggregate(base_child, metric_col=metric_col, agg=agg)
        delta = cur_val - base_val
        slices.append(
            DrillSlice(
                label=str(child_val),
                parent=parent_value,
                child=child_val,
                baseline_value=base_val,
                current_value=cur_val,
                delta=delta,
                sample_size=int(len(grp)),
            )
        )

    sorted_by_delta = sorted(slices, key=lambda x: abs(x.delta), reverse=True)[:top_n]
    return DrillDownResult(
        parent_dimension=dimension,
        child_dimension=child_dimension,
        parent_value=parent_value,
        slices=slices,
        top_drivers=[s.to_dict() for s in sorted_by_delta],
    )


# ---------------------------------------------------------------------------
# Narrative stub
# ---------------------------------------------------------------------------


def render_narrative(
    result: WaterfallResult,
    *,
    kpi_name: str = "KPI",
) -> str:
    """Build a deterministic narrative template.

    The agent layer replaces placeholders with the LLM-generated
    story; this function is the structured skeleton.
    """
    direction = "increased" if result.total_delta > 0 else "decreased"
    magnitude = (
        "significantly"
        if abs(result.total_delta) > 0.05 * abs(result.baseline_total or 1.0)
        else "slightly"
    )
    if result.top_drivers:
        first = result.top_drivers[0]
        seg = first.get("segment", "?")
        delta = first.get("delta", 0.0)
        seg_clause = f"Top driver: {seg} contributed {delta:+.4f}."
    else:
        seg_clause = "No segments above 0."
    if result.top_drains:
        first = result.top_drains[0]
        seg = first.get("segment", "?")
        delta = first.get("delta", 0.0)
        drain_clause = f"Top drain: {seg} contributed {delta:+.4f}."
    else:
        drain_clause = "No negative contributions detected."
    return (
        f"{kpi_name} {direction} {magnitude} from {result.baseline_total:.4f} "
        f"to {result.current_total:.4f} (Δ={result.total_delta:+.4f}). "
        f"{seg_clause} {drain_clause}"
    )


__all__ = [
    "WaterfallSegment",
    "WaterfallResult",
    "DrillSlice",
    "DrillDownResult",
    "waterfall",
    "drill_down",
    "render_narrative",
]
