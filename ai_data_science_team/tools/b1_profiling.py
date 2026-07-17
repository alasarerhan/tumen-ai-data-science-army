from __future__ import annotations

"""Data profiling tools for the AI Data Science Team.

This module provides tools for analyzing and profiling datasets.
These tools are used by agents to understand data structure before processing.

Tools
-----
- profile_dataframe: Analyze column types, cardinality, and statistics
- infer_units: Infer measurement units from column names
- resolve_column_aliases: Match user-provided names to actual column names
"""

import difflib  # noqa: E402, F401
import re  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401

from ai_data_science_team.tool_registry import (  # noqa: E402, F401
    ToolParameter,
    register_tool,
)


@register_tool(
    name="profile_dataframe",
    description="Analyze a DataFrame to determine column types, cardinality, and statistics.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
    },
    returns="Dict with column types, cardinality, and statistics",
    namespace="core.profiling",
    capabilities=["profiling", "analysis", "schema", "statistics"],
    cost_tier="low",
)
def profile_dataframe(data: pd.DataFrame | dict) -> dict:
    """Profile a DataFrame to understand its structure.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.

    Returns
    -------
    dict
        Profile with:
        - n_rows: number of rows
        - columns: list of column names
        - numeric_cols: numeric columns
        - categorical_cols: categorical columns
        - datetime_cols: datetime columns
        - boolean_cols: boolean columns
        - low_cardinality_numeric: numeric columns with <=10 unique values
        - high_cardinality_categorical: categorical columns with high cardinality
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "n_rows": 0,
            "columns": [],
            "numeric_cols": [],
            "categorical_cols": [],
            "datetime_cols": [],
            "boolean_cols": [],
            "low_cardinality_numeric": [],
            "high_cardinality_categorical": [],
        }

    n_rows = len(df)
    sample = df.head(5000) if n_rows > 5000 else df

    columns = [str(c) for c in list(sample.columns)]
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    datetime_cols: list[str] = []
    boolean_cols: list[str] = []
    low_card_numeric: list[str] = []
    high_card_categorical: list[str] = []

    for col in columns:
        s = sample[col]
        try:
            nunique = int(s.nunique(dropna=True))
        except Exception:
            nunique = 0

        if pd.api.types.is_bool_dtype(s):
            boolean_cols.append(col)
            categorical_cols.append(col)
            continue
        if pd.api.types.is_datetime64_any_dtype(s):
            datetime_cols.append(col)
            continue
        if pd.api.types.is_numeric_dtype(s):
            numeric_cols.append(col)
            if nunique <= 10:
                low_card_numeric.append(col)
                categorical_cols.append(col)
            continue

        categorical_cols.append(col)
        if nunique >= max(20, int(0.2 * max(n_rows, 1))):
            high_card_categorical.append(col)

    return {
        "n_rows": n_rows,
        "columns": columns,
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "datetime_cols": datetime_cols,
        "boolean_cols": boolean_cols,
        "low_cardinality_numeric": low_card_numeric,
        "high_cardinality_categorical": high_card_categorical,
    }


@register_tool(
    name="infer_units",
    description="Infer measurement units from column names (e.g., 'age' -> 'years', 'price' -> 'USD').",
    parameters={
        "columns": ToolParameter(type="array", description="List of column names", required=True),
    },
    returns="Dict mapping column names to inferred units",
    namespace="core.profiling",
    capabilities=["profiling", "units", "metadata"],
    cost_tier="low",
)
def infer_units(columns: list[str]) -> dict[str, str]:
    """Infer measurement units from column names.

    Parameters
    ----------
    columns : list[str]
        List of column names.

    Returns
    -------
    dict
        Mapping of column names to inferred units.
    """
    units = {}
    for col in columns:
        col_lower = col.lower()
        unit = None
        if "%" in col_lower or "pct" in col_lower or "percent" in col_lower:
            unit = "%"
        elif "usd" in col_lower or "price" in col_lower or "amount" in col_lower:
            unit = "USD"
        elif "cost" in col_lower or "charge" in col_lower:
            unit = "USD"
        elif "date" in col_lower or "time" in col_lower:
            unit = "date/time"
        elif "age" in col_lower:
            unit = "years"
        elif col_lower.endswith("_id") or col_lower == "id":
            unit = None
        if unit:
            units[col] = unit
    return units


@register_tool(
    name="resolve_column_aliases",
    description="Match user-provided column names to actual DataFrame column names using fuzzy matching.",
    parameters={
        "text": ToolParameter(type="string", description="User-provided text to search for column names", required=True),
        "columns": ToolParameter(type="array", description="List of actual column names", required=True),
    },
    returns="Dict mapping user terms to actual column names",
    namespace="core.profiling",
    capabilities=["profiling", "matching", "fuzzy"],
    cost_tier="low",
)
def resolve_column_aliases(text: str, columns: list[str]) -> dict[str, str]:
    """Resolve column aliases using fuzzy matching.

    Parameters
    ----------
    text : str
        User-provided text to search for column names.
    columns : list[str]
        List of actual column names.

    Returns
    -------
    dict
        Mapping of user terms to actual column names.
    """
    def _normalize(value: str) -> str:
        if not isinstance(value, str):
            return ""
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    if not isinstance(text, str) or not text.strip():
        return {}
    columns = [str(c) for c in columns if isinstance(c, str)]
    if not columns:
        return {}

    col_norm_map = {c: _normalize(c) for c in columns}
    tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
    candidates = set(tokens)
    for i in range(len(tokens) - 1):
        candidates.add(tokens[i] + tokens[i + 1])
        candidates.add(f"{tokens[i]}_{tokens[i + 1]}")

    aliases: dict[str, str] = {}
    for cand in list(candidates):
        cand_norm = _normalize(cand)
        if not cand_norm or len(cand_norm) < 3:
            continue
        best = None
        best_score = 0.0
        for col, col_norm in col_norm_map.items():
            if not col_norm:
                continue
            if cand_norm == col_norm or cand_norm in col_norm:
                best = col
                best_score = 1.0
                break
            score = difflib.SequenceMatcher(None, cand_norm, col_norm).ratio()
            if score > best_score:
                best_score = score
                best = col
        if best and best_score >= 0.82:
            aliases[cand] = best
    return aliases


@register_tool(
    name="format_profile_for_prompt",
    description="Format a DataFrame profile for inclusion in an LLM prompt.",
    parameters={
        "profile": ToolParameter(type="object", description="Profile dict from profile_dataframe", required=True),
    },
    returns="Formatted string for LLM prompt",
    namespace="core.profiling",
    capabilities=["profiling", "formatting", "prompt"],
    cost_tier="low",
)
def format_profile_for_prompt(profile: dict) -> str:
    """Format a profile for LLM prompt.

    Parameters
    ----------
    profile : dict
        Profile from profile_dataframe.

    Returns
    -------
    str
        Formatted string.
    """
    if not isinstance(profile, dict):
        return ""

    def _fmt(values: list[str]) -> str:
        return ", ".join(values[:12]) if values else "None"

    return "\n".join(
        [
            f"Rows: {profile.get('n_rows')}",
            f"Numeric: {_fmt(profile.get('numeric_cols') or [])}",
            f"Categorical: {_fmt(profile.get('categorical_cols') or [])}",
            f"Datetime: {_fmt(profile.get('datetime_cols') or [])}",
            f"Boolean: {_fmt(profile.get('boolean_cols') or [])}",
            f"Low-card numeric: {_fmt(profile.get('low_cardinality_numeric') or [])}",
            f"High-card categorical: {_fmt(profile.get('high_cardinality_categorical') or [])}",
        ]
    )


PROFILING_TOOLS = [
    "profile_dataframe",
    "infer_units",
    "resolve_column_aliases",
    "format_profile_for_prompt",
]


__all__ = [
    "profile_dataframe",
    "infer_units",
    "resolve_column_aliases",
    "format_profile_for_prompt",
    "PROFILING_TOOLS",
]

# Compatibility shims — modernized profiling module dropped these names but the
# agent file expects them. Each is a thin forwarder to the modernized equivalent
# or a minimal local implementation.

def profile_column(series, *, top_categories=5, hist_bins=10):
    """Profile a single column — returns dict with dtype, null_rate, uniques, etc."""
    out = {
        "name": getattr(series, "name", None),
        "dtype": str(series.dtype),
        "n": int(len(series)),
        "null_rate": float(series.isna().mean()) if hasattr(series, "isna") else 0.0,
        "uniques": int(series.nunique(dropna=True)) if hasattr(series, "nunique") else None,
    }
    if out["null_rate"] is None:
        out["null_rate"] = 0.0
    if hasattr(series, "dtype") and series.dtype.kind in "fi":
        try:
            s = series.dropna().astype(float)
            if len(s):
                out["min"] = float(s.min())
                out["max"] = float(s.max())
                out["mean"] = float(s.mean())
                out["std"] = float(s.std())
        except Exception:
            pass
    elif hasattr(series, "dtype") and series.dtype.kind == "O":
        try:
            vc = series.value_counts().head(top_categories)
            out["top_categories"] = [(str(k), int(v)) for k, v in vc.items()]
        except Exception:
            pass
    return out
