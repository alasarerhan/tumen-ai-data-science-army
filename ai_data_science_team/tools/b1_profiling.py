"""
b1_profiling
============

Deterministic dataset profiling tools supporting **B1 — Data
Profiling Genişletmesi** (spec ``docs/specs/B1-data-profiling.md``).

Provides per-column statistical profiles plus a lightweight PII
signal detector and a dataset-level summary that the I2 catalog can
consume. The output is what ``catalog.columns[*].stats`` and the
column-card "Istatistik" tab render from.

Public surface
--------------

* :func:`profile_dataframe(df, *, include_pii_scan=True, sample_size=None)`
  → top-level ``DatasetProfile``.
* :func:`profile_column(series, *, name=None, pii_scan=True)` →
  ``ColumnProfile`` with summary + PII signal.
* :func:`_pii_scan(series, name)` → returns ``{"pii_signal", "pii_kind"}``.
* :func:`B1_PROFILING_TOOL_NAMES`` — registry constant.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import math
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# PII heuristics — regex + column-name sniff (matches B5 spec keywords).
# ---------------------------------------------------------------------------


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TURKISH_PHONE_RE = re.compile(r"^(?:\+?90|0)?\s?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$")
_TCKN_RE = re.compile(r"^\d{11}$")  # Turkish ID number (11 digits)
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{12,30}$")
_CARD_RE = re.compile(r"^(?:\d[ -]?){13,19}$")


PII_NAME_HINTS: Dict[str, str] = {
    "email": "email",
    "e_mail": "email",
    "mail": "email",
    "phone": "phone",
    "telefon": "phone",
    "tel": "phone",
    "mobile": "phone",
    "gsm": "phone",
    "tckn": "tckn",
    "tc_kimlik": "tckn",
    "identity": "tckn",
    "ssn": "ssn",
    "iban": "iban",
    "account": "iban",
    "card": "card",
    "credit_card": "card",
    "name": "name",
    "first_name": "name",
    "last_name": "name",
    "ad": "name",
    "soyad": "name",
    "address": "address",
    "adres": "address",
}


def _column_name_signal(name: str) -> Optional[str]:
    n = name.lower().replace("-", "_").strip()
    # Token-level match: split on underscores/spaces and look up tokens.
    tokens = [t for t in re.split(r"[_\s]+", n) if t]
    matched: List[str] = []
    for tok in tokens:
        if tok in PII_NAME_HINTS:
            matched.append(PII_NAME_HINTS[tok])
    if matched:
        # Most-specific hit wins; "tckn" beats "email" if both appear.
        order = ["card", "iban", "tckn", "ssn", "phone", "email", "name", "address"]
        for kind in order:
            if kind in matched:
                return kind
    return None


def _sample_strings(series: pd.Series, *, max_n: int = 100) -> List[str]:
    cleaned = series.dropna().astype(str).tolist()
    return cleaned[:max_n]


def _pii_scan(series: pd.Series, name: Optional[str]) -> Dict[str, Any]:
    """Lightweight PII heuristic over a column.

    Two signals combined:
      * column-name heuristic (PII_NAME_HINTS).
      * value-pattern heuristic over up to 100 non-null samples
        (email, phone, TCKN, IBAN, card).
    """
    name_hint = _column_name_signal(name or series.name or "")
    sample_strings = _sample_strings(series)

    signal = "low"
    kind: Optional[str] = None
    matched_ratio = 0.0

    if not sample_strings:
        if name_hint:
            signal = "warning"
            kind = name_hint
            return {"pii_signal": signal, "pii_kind": kind, "match_ratio": 0.0}

    # Value-pattern checks
    pattern_kinds: Dict[str, re.Pattern] = {
        "email": _EMAIL_RE,
        "phone": _TURKISH_PHONE_RE,
        "tckn": _TCKN_RE,
        "iban": _IBAN_RE,
        "card": _CARD_RE,
    }

    for kind_key, regex in pattern_kinds.items():
        matches = sum(1 for s in sample_strings if regex.match(s.strip()))
        if matches:
            r = matches / len(sample_strings)
            if r > matched_ratio:
                matched_ratio = r
                kind = kind_key
            if r >= 0.6:
                signal = "high"
            elif r >= 0.3:
                signal = "warning"

    if name_hint:
        # Promote the signal so the catalog flags the column.
        if signal == "low":
            signal = "warning"
        if kind is None:
            kind = name_hint

    return {
        "pii_signal": signal,
        "pii_kind": kind,
        "match_ratio": float(matched_ratio),
    }


# ---------------------------------------------------------------------------
# Column-level profile
# ---------------------------------------------------------------------------


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    n: int
    n_missing: int
    n_unique: int
    is_numeric: bool
    is_categorical: bool
    stats: Dict[str, Any]
    pii: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "n": self.n,
            "n_missing": self.n_missing,
            "n_unique": self.n_unique,
            "is_numeric": self.is_numeric,
            "is_categorical": self.is_categorical,
            "stats": dict(self.stats),
            "pii": dict(self.pii),
        }


def profile_column(
    series: pd.Series,
    *,
    name: Optional[str] = None,
    pii_scan: bool = True,
    max_top_n: int = 10,
) -> ColumnProfile:
    """Compute per-column profile including optional PII signal."""
    col_name = name or str(series.name or "")
    n = int(len(series))
    n_missing = int(series.isna().sum())
    n_unique = int(series.dropna().nunique())

    is_numeric = bool(pd.api.types.is_numeric_dtype(series))
    # `is_categorical_dtype` is deprecated in pandas 2.x; use
    # isinstance directly on the dtype for forward-compat.
    is_categorical = bool(
        pd.api.types.is_string_dtype(series)
        or isinstance(series.dtype, pd.CategoricalDtype)
    )

    stats: Dict[str, Any] = {}
    if is_numeric and n - n_missing > 0:
        non_null = series.dropna().astype(float)
        stats.update(
            {
                "min": float(non_null.min()),
                "max": float(non_null.max()),
                "mean": float(non_null.mean()),
                "median": float(non_null.median()),
                "std": float(non_null.std(ddof=0)) if n - n_missing > 1 else 0.0,
                "q01": float(non_null.quantile(0.01)),
                "q99": float(non_null.quantile(0.99)),
                "zeros": int((non_null == 0).sum()),
            }
        )
        # Histogram into 10 equal-width bins.
        try:
            counts, edges = np.histogram(non_null.to_numpy(), bins=10)
            stats["histogram"] = [
                {"lo": float(edges[i]), "hi": float(edges[i + 1]), "count": int(counts[i])}
                for i in range(len(counts))
            ]
        except (ValueError, TypeError):
            stats["histogram"] = []
    elif is_categorical and n - n_missing > 0:
        counts = series.dropna().value_counts()
        stats["top_values"] = [
            {"value": str(v), "count": int(c)}
            for v, c in counts.head(max_top_n).items()
        ]
    elif pd.api.types.is_datetime64_any_dtype(series) and n - n_missing > 0:
        ts = series.dropna()
        stats.update({"min": str(ts.min()), "max": str(ts.max())})

    pii: Dict[str, Any] = (
        _pii_scan(series, col_name)
        if pii_scan and (is_categorical or is_numeric)
        else {"pii_signal": "low", "pii_kind": None, "match_ratio": 0.0}
    )

    return ColumnProfile(
        name=col_name,
        dtype=str(series.dtype),
        n=n,
        n_missing=n_missing,
        n_unique=n_unique,
        is_numeric=is_numeric,
        is_categorical=is_categorical,
        stats=stats,
        pii=pii,
    )


# ---------------------------------------------------------------------------
# Dataset-level profile
# ---------------------------------------------------------------------------


@dataclass
class DatasetProfile:
    n_rows: int
    n_cols: int
    columns: List[ColumnProfile]
    pii_columns: List[str]
    schema_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_rows": self.n_rows,
            "n_cols": self.n_cols,
            "columns": [c.to_dict() for c in self.columns],
            "pii_columns": list(self.pii_columns),
            "schema_hash": self.schema_hash,
        }


def _schema_hash(df: pd.DataFrame) -> str:
    """Stable hash of a frame's schema (column names + dtypes).

    Format: lowercase hex of sha1, first 12 chars.
    """
    import hashlib

    s = "|".join(f"{c}:{df[c].dtype}" for c in df.columns)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def profile_dataframe(
    df: pd.DataFrame,
    *,
    include_pii_scan: bool = True,
    sample_size: Optional[int] = None,
) -> DatasetProfile:
    """Build a dataset-level profile.

    Parameters
    ----------
    df : pd.DataFrame
        The dataset to profile.
    include_pii_scan : bool
        Run the PII detector per column.  Disable for purely numeric
        signals-only flows when PII risk is already known.
    sample_size : int, optional
        If the frame has more rows than ``sample_size``, take a
        random subsample first (deterministic seed for reproducibility).
    """
    if df.shape[0] == 0 or df.shape[1] == 0:
        return DatasetProfile(
            n_rows=int(df.shape[0]),
            n_cols=int(df.shape[1]),
            columns=[],
            pii_columns=[],
            schema_hash=_schema_hash(df),
        )

    if sample_size is not None and df.shape[0] > sample_size:
        df = df.sample(n=sample_size, random_state=0).reset_index(drop=True)

    columns = [
        profile_column(df[c], name=str(c), pii_scan=include_pii_scan)
        for c in df.columns
    ]
    pii_columns = [c.name for c in columns if c.pii.get("pii_signal") in {"warning", "high"}]

    return DatasetProfile(
        n_rows=int(df.shape[0]),
        n_cols=int(df.shape[1]),
        columns=columns,
        pii_columns=pii_columns,
        schema_hash=_schema_hash(df),
    )


__all__ = [
    "ColumnProfile",
    "DatasetProfile",
    "profile_column",
    "profile_dataframe",
    "B1_PROFILING_TOOL_NAMES",
]


B1_PROFILING_TOOL_NAMES = [
    "b1_profile_column",
    "b1_profile_dataframe",
]
