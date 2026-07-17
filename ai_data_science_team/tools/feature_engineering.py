from __future__ import annotations

"""Feature engineering tools for the AI Data Science Team.

This module provides tools for feature engineering operations including
encoding, scaling, feature creation, and feature selection.

Tools
-----
- one_hot_encode: One-hot encode categorical columns
- label_encode: Label encode categorical columns
- create_datetime_features: Extract datetime components
- scale_features: Scale numeric features
- create_polynomial_features: Create polynomial features
- bin_numeric: Discretize numeric columns
- select_features: Select features based on importance
"""

from typing import List, Optional, Union  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401

from ai_data_science_team.tool_registry import (  # noqa: E402, F401
    ToolParameter,
    register_tool,
)


@register_tool(
    name="one_hot_encode",
    description="One-hot encode categorical columns.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "columns": ToolParameter(type="array", description="Columns to encode", required=True),
        "drop_first": ToolParameter(type="boolean", description="Drop first category to avoid multicollinearity", required=False, default=False),
    },
    returns="DataFrame with encoded columns as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "encoding", "categorical"],
    cost_tier="low",
)
def one_hot_encode(
    data: Union[pd.DataFrame, dict],
    columns: List[str],
    drop_first: bool = False,
) -> dict:
    """One-hot encode categorical columns.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    columns : List[str]
        Columns to encode.
    drop_first : bool
        Drop first category to avoid multicollinearity.

    Returns
    -------
    dict
        DataFrame with encoded columns as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    valid_cols = [c for c in columns if c in df.columns]
    if not valid_cols:
        return df.to_dict()

    df = pd.get_dummies(df, columns=valid_cols, drop_first=drop_first, dtype=int)
    return df.to_dict()


@register_tool(
    name="label_encode",
    description="Label encode categorical columns to integers.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "columns": ToolParameter(type="array", description="Columns to encode", required=True),
    },
    returns="DataFrame with encoded columns as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "encoding", "categorical"],
    cost_tier="low",
)
def label_encode(
    data: Union[pd.DataFrame, dict],
    columns: List[str],
) -> dict:
    """Label encode categorical columns to integers.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    columns : List[str]
        Columns to encode.

    Returns
    -------
    dict
        DataFrame with encoded columns as dictionary.
    """
    from sklearn.preprocessing import LabelEncoder  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    for col in columns:
        if col in df.columns:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))

    return df.to_dict()


@register_tool(
    name="create_datetime_features",
    description="Extract datetime components (year, month, day, hour, etc.) from datetime columns.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "column": ToolParameter(type="string", description="Datetime column to extract from", required=True),
        "features": ToolParameter(type="array", description="Features to extract: year, month, day, hour, minute, dayofweek, quarter", required=False),
    },
    returns="DataFrame with datetime features as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "datetime", "features"],
    cost_tier="low",
)
def create_datetime_features(
    data: Union[pd.DataFrame, dict],
    column: str,
    features: Optional[List[str]] = None,
) -> dict:
    """Extract datetime components from datetime columns.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    column : str
        Datetime column to extract from.
    features : List[str], optional
        Features to extract. Defaults to all.

    Returns
    -------
    dict
        DataFrame with datetime features as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    if features is None:
        features = ["year", "month", "day", "hour", "minute", "dayofweek", "quarter"]

    dt_col = pd.to_datetime(df[column], errors="coerce")

    prefix = column
    if "year" in features:
        df[f"{prefix}_year"] = dt_col.dt.year
    if "month" in features:
        df[f"{prefix}_month"] = dt_col.dt.month
    if "day" in features:
        df[f"{prefix}_day"] = dt_col.dt.day
    if "hour" in features:
        df[f"{prefix}_hour"] = dt_col.dt.hour
    if "minute" in features:
        df[f"{prefix}_minute"] = dt_col.dt.minute
    if "dayofweek" in features:
        df[f"{prefix}_dayofweek"] = dt_col.dt.dayofweek
    if "quarter" in features:
        df[f"{prefix}_quarter"] = dt_col.dt.quarter
    if "is_weekend" in features:
        df[f"{prefix}_is_weekend"] = (dt_col.dt.dayofweek >= 5).astype(int)

    return df.to_dict()


@register_tool(
    name="scale_features",
    description="Scale numeric features using StandardScaler or MinMaxScaler.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "columns": ToolParameter(type="array", description="Columns to scale", required=True),
        "method": ToolParameter(type="string", description="Scaling method: standard or minmax", required=False, default="standard"),
    },
    returns="DataFrame with scaled columns as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "scaling", "normalization"],
    cost_tier="low",
)
def scale_features(
    data: Union[pd.DataFrame, dict],
    columns: List[str],
    method: str = "standard",
) -> dict:
    """Scale numeric features.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    columns : List[str]
        Columns to scale.
    method : str
        Scaling method: standard or minmax.

    Returns
    -------
    dict
        DataFrame with scaled columns as dictionary.
    """
    from sklearn.preprocessing import StandardScaler, MinMaxScaler  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    valid_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if not valid_cols:
        return df.to_dict()

    method = method.lower()
    if method == "standard":
        scaler = StandardScaler()
    elif method == "minmax":
        scaler = MinMaxScaler()
    else:
        raise ValueError(f"Unknown scaling method: {method}")

    df[valid_cols] = scaler.fit_transform(df[valid_cols].fillna(0))

    return df.to_dict()


@register_tool(
    name="create_polynomial_features",
    description="Create polynomial features from numeric columns.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "columns": ToolParameter(type="array", description="Columns to expand", required=True),
        "degree": ToolParameter(type="integer", description="Polynomial degree", required=False, default=2),
        "interaction_only": ToolParameter(type="boolean", description="Only interaction terms", required=False, default=False),
    },
    returns="DataFrame with polynomial features as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "polynomial", "features"],
    cost_tier="medium",
)
def create_polynomial_features(
    data: Union[pd.DataFrame, dict],
    columns: List[str],
    degree: int = 2,
    interaction_only: bool = False,
) -> dict:
    """Create polynomial features from numeric columns.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    columns : List[str]
        Columns to expand.
    degree : int
        Polynomial degree.
    interaction_only : bool
        Only interaction terms.

    Returns
    -------
    dict
        DataFrame with polynomial features as dictionary.
    """
    from sklearn.preprocessing import PolynomialFeatures  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    valid_cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    if not valid_cols:
        return df.to_dict()

    poly = PolynomialFeatures(degree=degree, interaction_only=interaction_only, include_bias=False)
    poly_features = poly.fit_transform(df[valid_cols].fillna(0))

    feature_names = poly.get_feature_names_out(valid_cols)
    poly_df = pd.DataFrame(poly_features, columns=feature_names, index=df.index)

    for col in poly_df.columns:
        if col not in df.columns:
            df[col] = poly_df[col]

    return df.to_dict()


@register_tool(
    name="bin_numeric",
    description="Discretize numeric columns into bins.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "column": ToolParameter(type="string", description="Column to bin", required=True),
        "bins": ToolParameter(type="integer", description="Number of bins", required=False, default=5),
        "labels": ToolParameter(type="array", description="Labels for bins (optional)", required=False),
        "strategy": ToolParameter(type="string", description="Binning strategy: uniform, quantile", required=False, default="uniform"),
    },
    returns="DataFrame with binned column as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "binning", "discretization"],
    cost_tier="low",
)
def bin_numeric(
    data: Union[pd.DataFrame, dict],
    column: str,
    bins: int = 5,
    labels: Optional[List[str]] = None,
    strategy: str = "uniform",
) -> dict:
    """Discretize numeric columns into bins.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    column : str
        Column to bin.
    bins : int
        Number of bins.
    labels : List[str], optional
        Labels for bins.
    strategy : str
        Binning strategy: uniform or quantile.

    Returns
    -------
    dict
        DataFrame with binned column as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    if strategy == "quantile":
        df[f"{column}_binned"] = pd.qcut(df[column], q=bins, labels=labels, duplicates="drop")
    else:
        df[f"{column}_binned"] = pd.cut(df[column], bins=bins, labels=labels)

    return df.to_dict()


@register_tool(
    name="select_features",
    description="Select features based on variance or correlation.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "target": ToolParameter(type="string", description="Target column for correlation-based selection", required=False),
        "threshold": ToolParameter(type="number", description="Variance or correlation threshold", required=False, default=0.01),
        "method": ToolParameter(type="string", description="Selection method: variance, correlation", required=False, default="variance"),
    },
    returns="DataFrame with selected features as dict",
    namespace="core.feature_engineering",
    capabilities=["feature_engineering", "selection", "features"],
    cost_tier="low",
)
def select_features(
    data: Union[pd.DataFrame, dict],
    target: Optional[str] = None,
    threshold: float = 0.01,
    method: str = "variance",
) -> dict:
    """Select features based on variance or correlation.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    target : str, optional
        Target column for correlation-based selection.
    threshold : float
        Variance or correlation threshold.
    method : str
        Selection method: variance or correlation.

    Returns
    -------
    dict
        DataFrame with selected features as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if method == "variance":
        from sklearn.feature_selection import VarianceThreshold  # noqa: E402, F401

        selector = VarianceThreshold(threshold=threshold)
        selector.fit(df[numeric_cols].fillna(0))
        selected_cols = [numeric_cols[i] for i, selected in enumerate(selector.get_support()) if selected]

    elif method == "correlation" and target:
        if target not in df.columns:
            raise ValueError(f"Target column '{target}' not found")

        correlations = df[numeric_cols].corrwith(df[target]).abs()
        selected_cols = correlations[correlations >= threshold].index.tolist()

    else:
        selected_cols = numeric_cols

    non_numeric = [c for c in df.columns if c not in numeric_cols]
    result = df[selected_cols + non_numeric]

    return result.to_dict()


FEATURE_ENGINEERING_TOOLS = [
    "one_hot_encode",
    "label_encode",
    "create_datetime_features",
    "scale_features",
    "create_polynomial_features",
    "bin_numeric",
    "select_features",
]


__all__ = [
    "one_hot_encode",
    "label_encode",
    "create_datetime_features",
    "scale_features",
    "create_polynomial_features",
    "bin_numeric",
    "select_features",
    "FEATURE_ENGINEERING_TOOLS",
]
