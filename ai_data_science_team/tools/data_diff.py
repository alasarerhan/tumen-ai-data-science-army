from __future__ import annotations

"""j13_data_diff. Deterministic data-diff tools. Implements J13
— compare two dataset / run-version snapshots: row counts, schema
delta, per-column distribution shift (mean / std / null_rate /
cardinality), key-set differences, and a structured diff payload
for the UI.
"""

import math  # noqa: E402, F401
from dataclasses import dataclass  # noqa: E402, F401
from typing import Any, Dict, List, Optional, Set, Tuple  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401


@dataclass
class ColumnStats:
    name: str
    dtype: str
    n: int
    null_rate: float
    n_unique: int


@dataclass
class DiffSummary:
    rows_left: int
    rows_right: int
    rows_added: int
    rows_removed: int
    columns_added: List[str]
    columns_removed: List[str]
    columns_common: List[str]
    column_stats: Dict[str, Dict[str, Any]]
    drift_columns: List[str]


def _column_stats(s: pd.Series) -> ColumnStats:
    null_rate = float(s.isna().mean())
    s_non_null = s.dropna()
    return ColumnStats(
        name=str(s.name) if s.name is not None else "",
        dtype=str(s.dtype),
        n=int(len(s)),
        null_rate=null_rate,
        n_unique=int(s_non_null.nunique()),
    )


def profile_columns(df: pd.DataFrame) -> Dict[str, ColumnStats]:
    return {col: _column_stats(df[col]) for col in df.columns}


def _safe_float(x: Any) -> float:
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return float("nan")
        return v
    except (TypeError, ValueError):
        return float("nan")


def numeric_shift(
    left: pd.Series, right: pd.Series
) -> Dict[str, float]:
    """Return mean / std / null_rate shift for a numeric column.
    std_*-shift only meaningful if both sides have >=2 numeric
    values."""
    l_null = float(left.isna().mean())
    r_null = float(right.isna().mean())
    l = left.dropna()  # noqa: E741
    r = right.dropna()
    out: Dict[str, float] = {
        "left_mean": _safe_float(l.mean()) if len(l) else float("nan"),
        "right_mean": _safe_float(r.mean()) if len(r) else float("nan"),
        "mean_shift": _safe_float(r.mean() - l.mean()) if len(l) and len(r) else float("nan"),
        "left_std": _safe_float(l.std(ddof=0)) if len(l) > 1 else 0.0,
        "right_std": _safe_float(r.std(ddof=0)) if len(r) > 1 else 0.0,
        "null_rate_left": l_null,
        "null_rate_right": r_null,
        "cardinality_left": int(l.nunique()),
        "cardinality_right": int(r.nunique()),
    }
    return out


def schema_delta(
    left: pd.DataFrame, right: pd.DataFrame
) -> Tuple[List[str], List[str], List[str]]:
    l_cols = set(left.columns)
    r_cols = set(right.columns)
    return (
        sorted(r_cols - l_cols),
        sorted(l_cols - r_cols),
        sorted(l_cols & r_cols),
    )


def key_set_diff(
    left: pd.DataFrame, right: pd.DataFrame, key: str
) -> Tuple[Set[Any], Set[Any]]:
    """Return (keys_only_in_left, keys_only_in_right)."""
    if key not in left.columns or key not in right.columns:
        raise KeyError(f"key column not present in both sides: {key}")
    return (
        set(left[key].unique()) - set(right[key].unique()),
        set(right[key].unique()) - set(left[key].unique()),
    )


def diff_summary(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    key: Optional[str] = None,
    drift_threshold: float = 0.10,
) -> DiffSummary:
    """Full structural + distribution diff.

    If key is provided, rows_added / rows_removed come from key-set
    diff. Otherwise they're row-count deltas.
    """
    if key is not None:
        only_l, only_r = key_set_diff(left, right, key)
        rows_added = len(only_r)
        rows_removed = len(only_l)
    else:
        rows_added = max(0, len(right) - len(left))
        rows_removed = max(0, len(left) - len(right))
    cols_added, cols_removed, cols_common = schema_delta(left, right)
    stats: Dict[str, Dict[str, Any]] = {}
    drift: List[str] = []
    for col in cols_common:
        ls = left[col]
        rs = right[col]
        if pd.api.types.is_numeric_dtype(ls) and pd.api.types.is_numeric_dtype(rs):
            s = numeric_shift(ls, rs)
            stats[col] = s
            if abs(s["mean_shift"]) >= drift_threshold and not math.isnan(s["mean_shift"]):
                drift.append(col)
        else:
            stats[col] = {
                "left_mean": float("nan"),
                "right_mean": float("nan"),
                "mean_shift": float("nan"),
                "left_std": float("nan"),
                "right_std": float("nan"),
                "null_rate_left": float(ls.isna().mean()),
                "null_rate_right": float(rs.isna().mean()),
                "cardinality_left": int(ls.nunique()),
                "cardinality_right": int(rs.nunique()),
            }
            null_delta = abs(stats[col]["null_rate_right"] - stats[col]["null_rate_left"])
            if null_delta >= drift_threshold:
                drift.append(col)
    return DiffSummary(
        rows_left=int(len(left)),
        rows_right=int(len(right)),
        rows_added=rows_added,
        rows_removed=rows_removed,
        columns_added=cols_added,
        columns_removed=cols_removed,
        columns_common=cols_common,
        column_stats=stats,
        drift_columns=drift,
    )


def diff_payload(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    key: Optional[str] = None,
    drift_threshold: float = 0.10,
) -> Dict[str, Any]:
    s = diff_summary(left, right, key=key, drift_threshold=drift_threshold)
    return {
        "rows_left": s.rows_left,
        "rows_right": s.rows_right,
        "rows_added": s.rows_added,
        "rows_removed": s.rows_removed,
        "columns_added": s.columns_added,
        "columns_removed": s.columns_removed,
        "columns_common": s.columns_common,
        "column_stats": s.column_stats,
        "drift_columns": s.drift_columns,
    }


