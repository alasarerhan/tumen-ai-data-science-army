from __future__ import annotations

"""Data cleaning tools for the AI Data Science Team.

This module provides tools for data cleaning operations including
handling missing values, removing duplicates, and outlier detection.

Tools
-----
- remove_missing_columns: Drop columns with high missing percentage
- impute_missing: Impute missing values
- remove_duplicates: Remove duplicate rows
- remove_outliers: Remove outliers using IQR method
- convert_types: Convert column data types
"""

from typing import Any, List, Optional, Union  # noqa: E402, F401

import pandas as pd  # noqa: E402, F401

from ai_data_science_team.tool_registry import (  # noqa: E402, F401
    ToolParameter,
    register_tool,
)


@register_tool(
    name="remove_missing_columns",
    description="Remove columns with missing values above a threshold.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "threshold": ToolParameter(type="number", description="Missing value threshold (0-1)", required=False, default=0.4),
    },
    returns="DataFrame with columns removed as dict",
    namespace="core.cleaning",
    capabilities=["cleaning", "missing", "columns"],
    cost_tier="low",
)
def remove_missing_columns(
    data: Union[pd.DataFrame, dict],
    threshold: float = 0.4,
) -> dict:
    """Remove columns with missing values above a threshold.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    threshold : float
        Missing value threshold (0-1). Columns with missing > threshold are removed.

    Returns
    -------
    dict
        DataFrame with columns removed as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    missing_pct = df.isnull().sum() / len(df)
    cols_to_drop = missing_pct[missing_pct > threshold].index.tolist()

    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    return df.to_dict()


@register_tool(
    name="impute_missing",
    description="Impute missing values in a DataFrame.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "strategy": ToolParameter(type="string", description="Imputation strategy: mean, median, mode, constant", required=False, default="mean"),
        "fill_value": ToolParameter(type="any", description="Value for constant strategy", required=False),
        "columns": ToolParameter(type="array", description="Columns to impute (optional, defaults to all)", required=False),
    },
    returns="DataFrame with imputed values as dict",
    namespace="core.cleaning",
    capabilities=["cleaning", "missing", "imputation"],
    cost_tier="low",
)
def impute_missing(
    data: Union[pd.DataFrame, dict],
    strategy: str = "mean",
    fill_value: Any = None,
    columns: Optional[List[str]] = None,
) -> dict:
    """Impute missing values in a DataFrame.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    strategy : str
        Imputation strategy: mean, median, mode, constant.
    fill_value : Any
        Value for constant strategy.
    columns : List[str], optional
        Columns to impute. If None, imputes all columns.

    Returns
    -------
    dict
        DataFrame with imputed values as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if columns is None:
        columns = df.columns.tolist()

    strategy = strategy.lower()

    for col in columns:
        if col not in df.columns:
            continue

        if df[col].isnull().sum() == 0:
            continue

        if pd.api.types.is_numeric_dtype(df[col]):
            if strategy == "mean":
                df[col] = df[col].fillna(df[col].mean())
            elif strategy == "median":
                df[col] = df[col].fillna(df[col].median())
            elif strategy == "mode":
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col] = df[col].fillna(mode_val.iloc[0])
            elif strategy == "constant":
                df[col] = df[col].fillna(fill_value if fill_value is not None else 0)
        else:
            if strategy == "mode":
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col] = df[col].fillna(mode_val.iloc[0])
            elif strategy == "constant":
                df[col] = df[col].fillna(fill_value if fill_value is not None else "")

    return df.to_dict()


@register_tool(
    name="remove_duplicates",
    description="Remove duplicate rows from a DataFrame.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "subset": ToolParameter(type="array", description="Columns to consider for duplicates", required=False),
        "keep": ToolParameter(type="string", description="Which duplicates to keep: first, last, or none", required=False, default="first"),
    },
    returns="DataFrame with duplicates removed as dict",
    namespace="core.cleaning",
    capabilities=["cleaning", "duplicates"],
    cost_tier="low",
)
def remove_duplicates(
    data: Union[pd.DataFrame, dict],
    subset: Optional[List[str]] = None,
    keep: str = "first",
) -> dict:
    """Remove duplicate rows from a DataFrame.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    subset : List[str], optional
        Columns to consider for duplicates.
    keep : str
        Which duplicates to keep: first, last, or False (remove all).

    Returns
    -------
    dict
        DataFrame with duplicates removed as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if keep == "none":
        keep = False

    df = df.drop_duplicates(subset=subset, keep=keep)

    return df.to_dict()


@register_tool(
    name="remove_outliers",
    description="Remove outliers using IQR method.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "columns": ToolParameter(type="array", description="Columns to check for outliers", required=True),
        "iqr_multiplier": ToolParameter(type="number", description="IQR multiplier for outlier threshold", required=False, default=1.5),
    },
    returns="DataFrame with outliers removed as dict",
    namespace="core.cleaning",
    capabilities=["cleaning", "outliers"],
    cost_tier="low",
)
def remove_outliers(
    data: Union[pd.DataFrame, dict],
    columns: List[str],
    iqr_multiplier: float = 1.5,
) -> dict:
    """Remove outliers using IQR method.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    columns : List[str]
        Columns to check for outliers.
    iqr_multiplier : float
        IQR multiplier for outlier threshold.

    Returns
    -------
    dict
        DataFrame with outliers removed as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1

        lower_bound = Q1 - iqr_multiplier * IQR
        upper_bound = Q3 + iqr_multiplier * IQR

        df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]

    return df.to_dict()


@register_tool(
    name="convert_types",
    description="Convert column data types.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "column": ToolParameter(type="string", description="Column to convert", required=True),
        "dtype": ToolParameter(type="string", description="Target dtype: int, float, str, bool, datetime", required=True),
    },
    returns="DataFrame with converted types as dict",
    namespace="core.cleaning",
    capabilities=["cleaning", "types", "conversion"],
    cost_tier="low",
)
def convert_types(
    data: Union[pd.DataFrame, dict],
    column: str,
    dtype: str,
) -> dict:
    """Convert column data types.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    column : str
        Column to convert.
    dtype : str
        Target dtype: int, float, str, bool, datetime.

    Returns
    -------
    dict
        DataFrame with converted types as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    dtype = dtype.lower()

    if dtype == "int":
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")
    elif dtype == "float":
        df[column] = pd.to_numeric(df[column], errors="coerce")
    elif dtype == "str" or dtype == "string":
        df[column] = df[column].astype(str)
    elif dtype == "bool":
        df[column] = df[column].astype(bool)
    elif dtype == "datetime" or dtype == "date":
        df[column] = pd.to_datetime(df[column], errors="coerce")
    else:
        raise ValueError(f"Unknown dtype: {dtype}")

    return df.to_dict()


CLEANING_TOOLS = [
    "remove_missing_columns",
    "impute_missing",
    "remove_duplicates",
    "remove_outliers",
    "convert_types",
]


__all__ = [
    "remove_missing_columns",
    "impute_missing",
    "remove_duplicates",
    "remove_outliers",
    "convert_types",
    "CLEANING_TOOLS",
]
