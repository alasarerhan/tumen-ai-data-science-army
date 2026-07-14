"""
c1_insight
==========

Deterministic insight-mining tools supporting **C1 — Insight Mining
(EDA eki)** (spec ``docs/specs/C1-insight-mining.md``).

Companion to the EDA / data-profiling pipeline.  When an analyst
or agent profiles a dataset, the deterministic core here surfaces
the *interesting* segments/correlations/anomalies automatically
so the UI can render a feed of insight cards.

Public surface
--------------

* :func:`find_anomalies` — per-column z-score anomaly flagging.
* :func:`find_strong_correlations` — top-k correlated column pairs.
* :func:`find_skewness` — heavy-tail / skewness insights.
* :func:`find_missing_patterns` — per-column missing-rate + co-missing
  pairs.
* :func:`find_class_imbalance` — for low-cardinality columns that
  might be targets.
* :func:`mine_insights` — orchestrator that runs all of the above
  and returns a ranked list of Insight cards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Finding dataclasses
# ---------------------------------------------------------------------------


# Canonical finding kinds
KIND_ANOMALY = "anomaly"
KIND_CORRELATION = "correlation"
KIND_SKEW = "skew"
KIND_MISSING = "missing"
KIND_IMBALANCE = "class_imbalance"
KIND_CONSTANT = "constant"
KIND_OUTLIER = "outlier"

ALL_KINDS: List[str] = [
    KIND_ANOMALY,
    KIND_CORRELATION,
    KIND_SKEW,
    KIND_MISSING,
    KIND_IMBALANCE,
    KIND_CONSTANT,
    KIND_OUTLIER,
]


@dataclass
class Insight:
    kind: str
    title: str
    description: str
    columns: List[str] = field(default_factory=list)
    score: float = 0.0  # 0..1 — higher is more "interesting"
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "columns": list(self.columns),
            "score": float(self.score),
            "evidence": dict(self.evidence),
        }


# ---------------------------------------------------------------------------
# Per-finding routines
# ---------------------------------------------------------------------------


def find_anomalies(
    df: pd.DataFrame,
    *,
    z_threshold: float = 3.0,
    min_severity: float = 0.0,
) -> List[Insight]:
    """Return insights for columns whose values are extreme z-scores.

    Each numeric column is summarised; if its top-|z|-value
    exceeds ``z_threshold`` an insight is returned.  The score is
    ``min(1, max_z / (z_threshold * 2))`` so the severity bucket
    of the platform (None / moderate / significant) is captured.
    """
    out: List[Insight] = []
    for col in df.columns:
        series = df[col]
        if not _is_numeric(series):
            continue
        clean = series.dropna().astype(float)
        if len(clean) < 5:
            continue
        mu = float(clean.mean())
        sd = float(clean.std(ddof=0))
        if sd == 0 or not math.isfinite(sd):
            continue
        z = ((clean - mu) / sd).abs()
        max_z = float(z.max())
        if max_z < z_threshold:
            continue
        # Severity bucket
        sev = (
            "significant" if max_z >= 5.0
            else "moderate" if max_z >= 4.0
            else "low"
        )
        if max_z / (z_threshold * 2) < min_severity:
            continue
        out.append(
            Insight(
                kind=KIND_ANOMALY,
                title=f"Anomalous values in `{col}`",
                description=(
                    f"Column `{col}` contains at least one value with "
                    f"|z|={max_z:.2f} (severity: {sev})."
                ),
                columns=[col],
                score=float(min(1.0, max_z / (z_threshold * 2.0))),
                evidence={
                    "max_abs_z": max_z,
                    "severity": sev,
                    "n_rows": int(len(clean)),
                },
            )
        )
    return out


def find_strong_correlations(
    df: pd.DataFrame,
    *,
    top_k: int = 5,
    threshold: float = 0.7,
) -> List[Insight]:
    """Return insights for column pairs with |corr| ≥ threshold."""
    numeric = df.select_dtypes(include=[np.number]).dropna()
    if numeric.shape[1] < 2 or len(numeric) < 5:
        return []
    corr = numeric.corr().abs()
    pairs: List[Tuple[str, str, float]] = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = float(corr.iloc[i, j])
            if not math.isfinite(r):
                continue
            if r >= threshold:
                pairs.append((cols[i], cols[j], r))
    pairs.sort(key=lambda t: t[2], reverse=True)
    out: List[Insight] = []
    for a, b, r in pairs[:top_k]:
        out.append(
            Insight(
                kind=KIND_CORRELATION,
                title=f"Strong correlation: `{a}` ↔ `{b}`",
                description=(
                    f"Pearson |r|={r:.2f} between `{a}` and `{b}` — "
                    "worth a correlation panel and a follow-up scatter."
                ),
                columns=[a, b],
                score=float(min(1.0, r)),
                evidence={"abs_corr": r},
            )
        )
    return out


def find_skewness(
    df: pd.DataFrame,
    *,
    abs_threshold: float = 1.0,
) -> List[Insight]:
    """Return insights for numeric columns with heavy skew."""
    out: List[Insight] = []
    for col in df.columns:
        series = df[col]
        if not _is_numeric(series):
            continue
        clean = series.dropna().astype(float)
        if len(clean) < 8:
            continue
        skew = float(_skew(clean))
        if abs(skew) < abs_threshold:
            continue
        out.append(
            Insight(
                kind=KIND_SKEW,
                title=f"Skewed distribution in `{col}`",
                description=(
                    f"Column `{col}` has skew={skew:+.2f} (|skew| ≥ "
                    f"{abs_threshold:.1f}); consider a log or power transform."
                ),
                columns=[col],
                score=float(min(1.0, abs(skew) / 3.0)),
                evidence={"skew": skew},
            )
        )
    return out


def find_missing_patterns(
    df: pd.DataFrame,
    *,
    rate_threshold: float = 0.05,
) -> List[Insight]:
    """Return insights for columns with high null rate and
    co-missing pairs (A and B missing together)."""
    out: List[Insight] = []
    if df.shape[0] == 0:
        return out
    rates = df.isna().mean()
    high = [c for c in df.columns if rates[c] > rate_threshold]
    for c in high:
        rate = float(rates[c])
        out.append(
            Insight(
                kind=KIND_MISSING,
                title=f"High null rate in `{c}`",
                description=(
                    f"{rate*100:.1f}% of `{c}` is missing; either impute "
                    "or drop the column."
                ),
                columns=[c],
                score=float(min(1.0, rate * 2.0)),
                evidence={"null_rate": rate, "n_rows": int(len(df))},
            )
        )
    # Co-missing pairs (only on numeric subset for the corr heatmap)
    num = df.select_dtypes(include=[np.number])
    if num.shape[1] >= 2:
        miss = num.isna().astype(int)
        co = miss.corr().abs()
        seen: set = set()
        for i, a in enumerate(co.columns):
            for b in co.columns[i + 1:]:
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                r = float(co.iloc[i, co.columns.get_loc(b)])
                if math.isfinite(r) and r >= 0.7:
                    out.append(
                        Insight(
                            kind=KIND_MISSING,
                            title=f"Co-missing: `{a}` and `{b}`",
                            description=(
                                f"Columns `{a}` and `{b}` are missing "
                                f"together (corr={r:.2f}); a single "
                                "ingest step may be the cause."
                            ),
                            columns=[a, b],
                            score=float(min(1.0, r)),
                            evidence={"co_missing_corr": r},
                        )
                    )
    return out


def find_class_imbalance(
    df: pd.DataFrame,
    *,
    top_k: int = 3,
    min_imbalance: float = 0.85,
) -> List[Insight]:
    """Flag low-cardinality columns with skewed class distribution."""
    out: List[Insight] = []
    for col in df.columns:
        series = df[col]
        if not _is_low_cardinality(series, max_unique=20):
            continue
        counts = series.dropna().value_counts()
        if len(counts) < 2:
            continue
        top = float(counts.iloc[0]) / float(counts.sum())
        if top < min_imbalance:
            continue
        out.append(
            Insight(
                kind=KIND_IMBALANCE,
                title=f"Class imbalance in `{col}`",
                description=(
                    f"Top class of `{col}` is {top*100:.1f}% of "
                    f"non-null rows; consider class-weight / resampling."
                ),
                columns=[col],
                score=float(min(1.0, top)),
                evidence={
                    "top_class": str(counts.index[0]),
                    "top_class_share": top,
                    "n_classes": int(len(counts)),
                },
            )
        )
    return out[:top_k]


def find_constants_and_outliers(
    df: pd.DataFrame,
    *,
    top_k: int = 3,
    constant_min_unique: int = 1,
) -> List[Insight]:
    """Single-value columns (zero variance) — useless for ML."""
    out: List[Insight] = []
    for col in df.columns:
        nunique = int(df[col].nunique(dropna=True))
        if nunique <= constant_min_unique:
            out.append(
                Insight(
                    kind=KIND_CONSTANT,
                    title=f"Constant column `{col}`",
                    description=(
                        f"`{col}` has {nunique} distinct values; "
                        "drop it before training."
                    ),
                    columns=[col],
                    score=1.0,
                    evidence={"n_unique": nunique},
                )
            )
    return out[:top_k]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def mine_insights(
    df: pd.DataFrame,
    *,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
    top_k: int = 20,
    z_threshold: float = 3.0,
    corr_threshold: float = 0.7,
    skew_threshold: float = 1.0,
    null_threshold: float = 0.05,
) -> List[Dict[str, Any]]:
    """Run the full insight pipeline and return the top insights.

    ``include`` / ``exclude`` let the caller restrict which columns
    are scanned (e.g. only feature columns).
    """
    work = _filter_columns(df, include=include, exclude=exclude)
    if work.shape[1] == 0 or work.shape[0] == 0:
        return []
    findings: List[Insight] = []
    findings.extend(find_anomalies(work, z_threshold=z_threshold))
    findings.extend(
        find_strong_correlations(work, top_k=top_k, threshold=corr_threshold)
    )
    findings.extend(find_skewness(work, abs_threshold=skew_threshold))
    findings.extend(find_missing_patterns(work, rate_threshold=null_threshold))
    findings.extend(find_class_imbalance(work, top_k=top_k, min_imbalance=0.85))
    findings.extend(find_constants_and_outliers(work, top_k=top_k))
    findings.sort(key=lambda i: i.score, reverse=True)
    out = [i.to_dict() for i in findings[:top_k]]
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_numeric(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series):
        return True
    if pd.api.types.is_string_dtype(series):
        coerced = pd.to_numeric(series, errors="coerce")
        return coerced.notna().mean() > 0.5
    return False


def _is_low_cardinality(series: pd.Series, *, max_unique: int) -> bool:
    return int(series.dropna().nunique()) <= max_unique


def _skew(x: np.ndarray) -> float:
    """Pearson skewness — robust to small samples."""
    n = x.size
    if n < 3:
        return 0.0
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if sd == 0:
        return 0.0
    m3 = float(((x - mu) ** 3).mean())
    return m3 / (sd ** 3)


def _filter_columns(
    df: pd.DataFrame, *, include: Optional[Sequence[str]], exclude: Optional[Sequence[str]]
) -> pd.DataFrame:
    cols = list(df.columns)
    if include is not None:
        cols = [c for c in cols if c in include]
    if exclude is not None:
        cols = [c for c in cols if c not in set(exclude)]
    return df[cols]


__all__ = [
    "KIND_ANOMALY",
    "KIND_CORRELATION",
    "KIND_SKEW",
    "KIND_MISSING",
    "KIND_IMBALANCE",
    "KIND_CONSTANT",
    "KIND_OUTLIER",
    "ALL_KINDS",
    "Insight",
    "find_anomalies",
    "find_strong_correlations",
    "find_skewness",
    "find_missing_patterns",
    "find_class_imbalance",
    "find_constants_and_outliers",
    "mine_insights",
]


