"""Data wrangling tools for the AI Data Science Team.

This module provides tools for data transformation, filtering, aggregation,
and reshaping operations. These tools are used by DataWranglingAgent and
other data processing agents.

Tools
-----
- filter_rows: Filter DataFrame by conditions
- select_columns: Select specific columns
- rename_columns: Rename columns
- aggregate_data: GroupBy aggregations
- merge_datasets: Join/merge multiple DataFrames
- pivot_data: Pivot and melt operations
- transform_column: Apply transformations to columns
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd

from ai_data_science_team.tool_registry import (
    ToolRegistry,
    ToolDefinition,
    ToolParameter,
    register_tool,
)


@register_tool(
    name="filter_rows",
    description="Filter DataFrame rows based on conditions.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "column": ToolParameter(type="string", description="Column to filter on", required=True),
        "operator": ToolParameter(type="string", description="Comparison operator: ==, !=, >, <, >=, <=, in, not_in, contains", required=True),
        "value": ToolParameter(type="any", description="Value to compare against", required=True),
    },
    returns="Filtered DataFrame as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "filter", "subset"],
    cost_tier="low",
)
def filter_rows(
    data: Union[pd.DataFrame, dict],
    column: str,
    operator: str,
    value: Any,
) -> dict:
    """Filter DataFrame rows based on conditions.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    column : str
        Column to filter on.
    operator : str
        Comparison operator: ==, !=, >, <, >=, <=, in, not_in, contains.
    value : Any
        Value to compare against.

    Returns
    -------
    dict
        Filtered DataFrame as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    operator = operator.strip().lower()

    if operator == "==" or operator == "eq":
        result = df[df[column] == value]
    elif operator == "!=" or operator == "ne":
        result = df[df[column] != value]
    elif operator == ">" or operator == "gt":
        result = df[df[column] > value]
    elif operator == "<" or operator == "lt":
        result = df[df[column] < value]
    elif operator == ">=" or operator == "ge":
        result = df[df[column] >= value]
    elif operator == "<=" or operator == "le":
        result = df[df[column] <= value]
    elif operator == "in":
        result = df[df[column].isin(value if isinstance(value, list) else [value])]
    elif operator == "not_in":
        result = df[~df[column].isin(value if isinstance(value, list) else [value])]
    elif operator == "contains":
        result = df[df[column].astype(str).str.contains(str(value), case=False, na=False)]
    elif operator == "is_null" or operator == "isna":
        result = df[df[column].isna()]
    elif operator == "not_null" or operator == "notna":
        result = df[df[column].notna()]
    else:
        raise ValueError(f"Unknown operator: {operator}")

    return result.to_dict()


@register_tool(
    name="select_columns",
    description="Select specific columns from a DataFrame.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "columns": ToolParameter(type="array", description="List of column names to select", required=True),
        "exclude": ToolParameter(type="boolean", description="If True, exclude specified columns", required=False, default=False),
    },
    returns="DataFrame with selected columns as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "select", "columns"],
    cost_tier="low",
)
def select_columns(
    data: Union[pd.DataFrame, dict],
    columns: List[str],
    exclude: bool = False,
) -> dict:
    """Select specific columns from a DataFrame.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    columns : List[str]
        List of column names to select.
    exclude : bool
        If True, exclude specified columns.

    Returns
    -------
    dict
        DataFrame with selected columns as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if exclude:
        result = df.drop(columns=columns, errors="ignore")
    else:
        result = df[columns]

    return result.to_dict()


@register_tool(
    name="rename_columns",
    description="Rename columns in a DataFrame.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "mapping": ToolParameter(type="object", description="Dict mapping old names to new names", required=True),
    },
    returns="DataFrame with renamed columns as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "rename", "columns"],
    cost_tier="low",
)
def rename_columns(
    data: Union[pd.DataFrame, dict],
    mapping: Dict[str, str],
) -> dict:
    """Rename columns in a DataFrame.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    mapping : Dict[str, str]
        Dict mapping old names to new names.

    Returns
    -------
    dict
        DataFrame with renamed columns as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data
    result = df.rename(columns=mapping)
    return result.to_dict()


@register_tool(
    name="aggregate_data",
    description="Aggregate data using GroupBy operations.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "group_by": ToolParameter(type="array", description="Columns to group by", required=True),
        "agg_column": ToolParameter(type="string", description="Column to aggregate", required=True),
        "agg_func": ToolParameter(type="string", description="Aggregation function: sum, mean, count, min, max, std, var", required=True),
    },
    returns="Aggregated DataFrame as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "aggregate", "groupby"],
    cost_tier="low",
)
def aggregate_data(
    data: Union[pd.DataFrame, dict],
    group_by: Union[str, List[str]],
    agg_column: str,
    agg_func: str = "mean",
) -> dict:
    """Aggregate data using GroupBy operations.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    group_by : str or List[str]
        Columns to group by.
    agg_column : str
        Column to aggregate.
    agg_func : str
        Aggregation function: sum, mean, count, min, max, std, var.

    Returns
    -------
    dict
        Aggregated DataFrame as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if isinstance(group_by, str):
        group_by = [group_by]

    agg_func = agg_func.lower()

    if agg_func == "sum":
        result = df.groupby(group_by)[agg_column].sum().reset_index()
    elif agg_func == "mean" or agg_func == "avg":
        result = df.groupby(group_by)[agg_column].mean().reset_index()
    elif agg_func == "count":
        result = df.groupby(group_by)[agg_column].count().reset_index()
    elif agg_func == "min":
        result = df.groupby(group_by)[agg_column].min().reset_index()
    elif agg_func == "max":
        result = df.groupby(group_by)[agg_column].max().reset_index()
    elif agg_func == "std":
        result = df.groupby(group_by)[agg_column].std().reset_index()
    elif agg_func == "var":
        result = df.groupby(group_by)[agg_column].var().reset_index()
    elif agg_func == "median":
        result = df.groupby(group_by)[agg_column].median().reset_index()
    else:
        raise ValueError(f"Unknown aggregation function: {agg_func}")

    return result.to_dict()


@register_tool(
    name="merge_datasets",
    description="Merge two DataFrames using database-style join.",
    parameters={
        "left": ToolParameter(type="object", description="Left DataFrame as dict", required=True),
        "right": ToolParameter(type="object", description="Right DataFrame as dict", required=True),
        "on": ToolParameter(type="array", description="Column(s) to join on", required=True),
        "how": ToolParameter(type="string", description="Join type: inner, left, right, outer", required=False, default="inner"),
    },
    returns="Merged DataFrame as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "merge", "join"],
    cost_tier="low",
)
def merge_datasets(
    left: Union[pd.DataFrame, dict],
    right: Union[pd.DataFrame, dict],
    on: Union[str, List[str]],
    how: str = "inner",
) -> dict:
    """Merge two DataFrames using database-style join.

    Parameters
    ----------
    left : DataFrame or dict
        Left DataFrame.
    right : DataFrame or dict
        Right DataFrame.
    on : str or List[str]
        Column(s) to join on.
    how : str
        Join type: inner, left, right, outer.

    Returns
    -------
    dict
        Merged DataFrame as dictionary.
    """
    left_df = pd.DataFrame(left) if isinstance(left, dict) else left
    right_df = pd.DataFrame(right) if isinstance(right, dict) else right

    result = pd.merge(left_df, right_df, on=on, how=how)
    return result.to_dict()


@register_tool(
    name="pivot_data",
    description="Pivot or melt a DataFrame for reshaping.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "operation": ToolParameter(type="string", description="Operation: pivot or melt", required=True),
        "index": ToolParameter(type="array", description="Columns for index (pivot) or id_vars (melt)", required=False),
        "columns": ToolParameter(type="array", description="Columns for columns (pivot) or value_vars (melt)", required=False),
        "values": ToolParameter(type="string", description="Column for values", required=False),
    },
    returns="Reshaped DataFrame as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "pivot", "melt", "reshape"],
    cost_tier="low",
)
def pivot_data(
    data: Union[pd.DataFrame, dict],
    operation: str,
    index: Optional[Union[str, List[str]]] = None,
    columns: Optional[Union[str, List[str]]] = None,
    values: Optional[str] = None,
) -> dict:
    """Pivot or melt a DataFrame for reshaping.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    operation : str
        Operation: pivot or melt.
    index : str or List[str], optional
        Columns for index (pivot) or id_vars (melt).
    columns : str or List[str], optional
        Columns for columns (pivot) or value_vars (melt).
    values : str, optional
        Column for values.

    Returns
    -------
    dict
        Reshaped DataFrame as dictionary.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    operation = operation.lower()

    if operation == "pivot":
        if index is None or columns is None or values is None:
            raise ValueError("pivot requires index, columns, and values")
        result = df.pivot(index=index, columns=columns, values=values)
    elif operation == "melt":
        id_vars = index if isinstance(index, list) else [index] if index else None
        value_vars = columns if isinstance(columns, list) else [columns] if columns else None
        result = df.melt(id_vars=id_vars, value_vars=value_vars, var_name="variable", value_name="value")
    else:
        raise ValueError(f"Unknown operation: {operation}")

    return result.reset_index().to_dict()


@register_tool(
    name="transform_column",
    description="Apply a transformation to a column.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "column": ToolParameter(type="string", description="Column to transform", required=True),
        "transform": ToolParameter(type="string", description="Transform type: log, sqrt, abs, negate, uppercase, lowercase, strip", required=True),
        "new_column": ToolParameter(type="string", description="Name for new column (optional)", required=False),
    },
    returns="Transformed DataFrame as dict",
    namespace="core.wrangling",
    capabilities=["wrangling", "transform", "column"],
    cost_tier="low",
)
def transform_column(
    data: Union[pd.DataFrame, dict],
    column: str,
    transform: str,
    new_column: Optional[str] = None,
) -> dict:
    """Apply a transformation to a column.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    column : str
        Column to transform.
    transform : str
        Transform type: log, sqrt, abs, negate, uppercase, lowercase, strip.
    new_column : str, optional
        Name for new column. If None, overwrites original.

    Returns
    -------
    dict
        Transformed DataFrame as dictionary.
    """
    import numpy as np

    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")

    target = new_column or column
    transform = transform.lower()

    if transform == "log":
        df[target] = np.log(df[column].astype(float))
    elif transform == "sqrt":
        df[target] = np.sqrt(df[column].astype(float))
    elif transform == "abs":
        df[target] = np.abs(df[column])
    elif transform == "negate":
        df[target] = -df[column]
    elif transform == "uppercase":
        df[target] = df[column].astype(str).str.upper()
    elif transform == "lowercase":
        df[target] = df[column].astype(str).str.lower()
    elif transform == "strip":
        df[target] = df[column].astype(str).str.strip()
    elif transform == "round":
        df[target] = df[column].round()
    else:
        raise ValueError(f"Unknown transform: {transform}")

    return df.to_dict()


WRANGLING_TOOLS = [
    "filter_rows",
    "select_columns",
    "rename_columns",
    "aggregate_data",
    "merge_datasets",
    "pivot_data",
    "transform_column",
]


__all__ = [
    "filter_rows",
    "select_columns",
    "rename_columns",
    "aggregate_data",
    "merge_datasets",
    "pivot_data",
    "transform_column",
    "WRANGLING_TOOLS",
]
