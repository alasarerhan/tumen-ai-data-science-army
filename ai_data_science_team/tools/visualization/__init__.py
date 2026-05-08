"""Visualization tools for the AI Data Science Team.

This module provides tools for creating various chart types using Plotly.
Each tool is focused on a single chart type and can be used independently.

Tools
-----
- scatter_plot: Create scatter plots for two numeric variables
- bar_chart: Create bar charts for categorical data
- line_chart: Create line charts for time series
- histogram: Create histograms for distribution analysis
- box_plot: Create box plots for statistical summaries
- violin_plot: Create violin plots for distribution comparison
- heatmap: Create heatmaps for correlation matrices
- pie_chart: Create pie charts for proportions
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from ai_data_science_team.tool_registry import (
    ToolRegistry,
    ToolDefinition,
    ToolParameter,
    register_tool,
)


def _normalize_column_name(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _label_for_column(col: str, units: dict[str, str] | None = None) -> str:
    label = str(col).replace("_", " ").strip().title()
    if units and col in units:
        label = f"{label} ({units[col]})"
    return label


def _infer_units(columns: list[str]) -> dict[str, str]:
    units = {}
    for col in columns:
        col_lower = col.lower()
        if "%" in col_lower or "pct" in col_lower or "percent" in col_lower:
            units[col] = "%"
        elif "usd" in col_lower or "price" in col_lower or "amount" in col_lower:
            units[col] = "USD"
        elif "cost" in col_lower or "charge" in col_lower:
            units[col] = "USD"
        elif "date" in col_lower or "time" in col_lower:
            units[col] = "date/time"
        elif "age" in col_lower:
            units[col] = "years"
    return units


@register_tool(
    name="scatter_plot",
    description="Create a scatter plot to visualize the relationship between two numeric variables.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis", required=True),
        "y": ToolParameter(type="string", description="Column name for Y-axis", required=True),
        "color": ToolParameter(type="string", description="Column name for color grouping", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
        "trendline": ToolParameter(type="string", description="Add trendline: 'ols' or 'lowess'", required=False, default=None),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "scatter", "numeric", "correlation"],
    cost_tier="low",
)
def scatter_plot(
    data: pd.DataFrame | dict,
    x: str,
    y: str,
    color: str | None = None,
    title: str | None = None,
    trendline: str | None = None,
    **kwargs,
) -> dict:
    """Create a scatter plot.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str
        Column for X-axis.
    y : str
        Column for Y-axis.
    color : str, optional
        Column for color encoding.
    title : str, optional
        Chart title.
    trendline : str, optional
        Add trendline ('ols' or 'lowess').

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data
    columns = list(df.columns)
    units = _infer_units(columns)

    fig = px.scatter(
        df,
        x=x,
        y=y,
        color=color,
        trendline=trendline,
        labels={
            x: _label_for_column(x, units),
            y: _label_for_column(y, units),
        },
        title=title or f"{_label_for_column(y, units)} vs {_label_for_column(x, units)}",
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="bar_chart",
    description="Create a bar chart to compare values across categories.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis (categories)", required=True),
        "y": ToolParameter(type="string", description="Column name for Y-axis (values)", required=True),
        "color": ToolParameter(type="string", description="Column name for color grouping", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
        "orientation": ToolParameter(type="string", description="Bar orientation: 'v' or 'h'", required=False, default="v"),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "bar", "categorical", "comparison"],
    cost_tier="low",
)
def bar_chart(
    data: pd.DataFrame | dict,
    x: str,
    y: str,
    color: str | None = None,
    title: str | None = None,
    orientation: str = "v",
    **kwargs,
) -> dict:
    """Create a bar chart.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str
        Column for categories.
    y : str
        Column for values.
    color : str, optional
        Column for color encoding.
    title : str, optional
        Chart title.
    orientation : str
        'v' for vertical, 'h' for horizontal.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data
    columns = list(df.columns)
    units = _infer_units(columns)

    fig = px.bar(
        df,
        x=x if orientation == "v" else y,
        y=y if orientation == "v" else x,
        color=color,
        orientation=orientation,
        labels={
            x: _label_for_column(x, units),
            y: _label_for_column(y, units),
        },
        title=title or f"{_label_for_column(y, units)} by {_label_for_column(x, units)}",
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="line_chart",
    description="Create a line chart to visualize trends over time or ordered categories.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis (typically time)", required=True),
        "y": ToolParameter(type="string", description="Column name for Y-axis", required=True),
        "color": ToolParameter(type="string", description="Column name for color grouping", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "line", "time-series", "trend"],
    cost_tier="low",
)
def line_chart(
    data: pd.DataFrame | dict,
    x: str,
    y: str,
    color: str | None = None,
    title: str | None = None,
    **kwargs,
) -> dict:
    """Create a line chart.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str
        Column for X-axis (typically time).
    y : str
        Column for Y-axis.
    color : str, optional
        Column for color encoding.
    title : str, optional
        Chart title.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data
    columns = list(df.columns)
    units = _infer_units(columns)

    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        labels={
            x: _label_for_column(x, units),
            y: _label_for_column(y, units),
        },
        title=title or f"{_label_for_column(y, units)} over {_label_for_column(x, units)}",
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="histogram",
    description="Create a histogram to visualize the distribution of a numeric variable.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis", required=True),
        "color": ToolParameter(type="string", description="Column name for color grouping", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
        "nbins": ToolParameter(type="integer", description="Number of bins", required=False, default=10),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "histogram", "distribution", "numeric"],
    cost_tier="low",
)
def histogram(
    data: pd.DataFrame | dict,
    x: str,
    color: str | None = None,
    title: str | None = None,
    nbins: int = 10,
    **kwargs,
) -> dict:
    """Create a histogram.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str
        Column for distribution.
    color : str, optional
        Column for color encoding.
    title : str, optional
        Chart title.
    nbins : int
        Number of bins.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data
    columns = list(df.columns)
    units = _infer_units(columns)

    fig = px.histogram(
        df,
        x=x,
        color=color,
        nbins=nbins,
        labels={x: _label_for_column(x, units)},
        title=title or f"Distribution of {_label_for_column(x, units)}",
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="box_plot",
    description="Create a box plot to visualize statistical summaries (median, quartiles, outliers).",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis (grouping)", required=False),
        "y": ToolParameter(type="string", description="Column name for Y-axis (values)", required=True),
        "color": ToolParameter(type="string", description="Column name for color grouping", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "box", "statistics", "distribution"],
    cost_tier="low",
)
def box_plot(
    data: pd.DataFrame | dict,
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    title: str | None = None,
    **kwargs,
) -> dict:
    """Create a box plot.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str, optional
        Column for grouping.
    y : str
        Column for values.
    color : str, optional
        Column for color encoding.
    title : str, optional
        Chart title.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data
    columns = list(df.columns)
    units = _infer_units(columns)

    fig = px.box(
        df,
        x=x,
        y=y,
        color=color,
        labels={
            x: _label_for_column(x, units) if x else "",
            y: _label_for_column(y, units) if y else "",
        },
        title=title or f"Distribution of {_label_for_column(y, units)}" + (f" by {_label_for_column(x, units)}" if x else ""),
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="violin_plot",
    description="Create a violin plot to visualize distribution shape and density.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis (grouping)", required=False),
        "y": ToolParameter(type="string", description="Column name for Y-axis (values)", required=True),
        "color": ToolParameter(type="string", description="Column name for color grouping", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
        "box": ToolParameter(type="boolean", description="Show embedded box plot", required=False, default=False),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "violin", "distribution", "density"],
    cost_tier="low",
)
def violin_plot(
    data: pd.DataFrame | dict,
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    title: str | None = None,
    box: bool = False,
    **kwargs,
) -> dict:
    """Create a violin plot.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str, optional
        Column for grouping.
    y : str
        Column for values.
    color : str, optional
        Column for color encoding.
    title : str, optional
        Chart title.
    box : bool
        Show embedded box plot.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data
    columns = list(df.columns)
    units = _infer_units(columns)

    fig = px.violin(
        df,
        x=x,
        y=y,
        color=color,
        box=box,
        labels={
            x: _label_for_column(x, units) if x else "",
            y: _label_for_column(y, units) if y else "",
        },
        title=title or f"Distribution of {_label_for_column(y, units)}" + (f" by {_label_for_column(x, units)}" if x else ""),
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="heatmap",
    description="Create a heatmap to visualize correlation matrix or 2D data.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "x": ToolParameter(type="string", description="Column name for X-axis", required=False),
        "y": ToolParameter(type="string", description="Column name for Y-axis", required=False),
        "z": ToolParameter(type="string", description="Column name for color values", required=False),
        "title": ToolParameter(type="string", description="Chart title", required=False),
        "correlation": ToolParameter(type="boolean", description="Compute correlation matrix", required=False, default=False),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "heatmap", "correlation", "matrix"],
    cost_tier="low",
)
def heatmap(
    data: pd.DataFrame | dict,
    x: str | None = None,
    y: str | None = None,
    z: str | None = None,
    title: str | None = None,
    correlation: bool = False,
    **kwargs,
) -> dict:
    """Create a heatmap.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    x : str, optional
        Column for X-axis.
    y : str, optional
        Column for Y-axis.
    z : str, optional
        Column for color values.
    title : str, optional
        Chart title.
    correlation : bool
        Compute correlation matrix from numeric columns.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.graph_objects as go
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if correlation:
        numeric_df = df.select_dtypes(include="number")
        corr_matrix = numeric_df.corr()
        fig = px.imshow(
            corr_matrix,
            labels=dict(x="Variable", y="Variable", color="Correlation"),
            title=title or "Correlation Matrix",
            color_continuous_scale="RdBu_r",
            **kwargs,
        )
    elif x and y and z:
        fig = px.density_heatmap(
            df,
            x=x,
            y=y,
            z=z,
            title=title or f"Heatmap of {z}",
            **kwargs,
        )
    else:
        raise ValueError("Either correlation=True or x, y, z must be provided")

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


@register_tool(
    name="pie_chart",
    description="Create a pie chart to visualize proportions of a whole.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "values": ToolParameter(type="string", description="Column name for values", required=True),
        "names": ToolParameter(type="string", description="Column name for labels", required=True),
        "title": ToolParameter(type="string", description="Chart title", required=False),
    },
    returns="Plotly figure as JSON-serializable dict",
    namespace="core.visualization",
    capabilities=["visualization", "pie", "proportion", "categorical"],
    cost_tier="low",
)
def pie_chart(
    data: pd.DataFrame | dict,
    values: str,
    names: str,
    title: str | None = None,
    **kwargs,
) -> dict:
    """Create a pie chart.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    values : str
        Column for values.
    names : str
        Column for labels.
    title : str, optional
        Chart title.

    Returns
    -------
    dict
        Plotly figure as JSON dict.
    """
    import plotly.express as px
    import plotly.io as pio

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    fig = px.pie(
        df,
        values=values,
        names=names,
        title=title or f"Distribution by {names}",
        **kwargs,
    )

    fig.update_layout(template="plotly_white")
    return json.loads(pio.to_json(fig))


VISUALIZATION_TOOLS = [
    "scatter_plot",
    "bar_chart",
    "line_chart",
    "histogram",
    "box_plot",
    "violin_plot",
    "heatmap",
    "pie_chart",
]


def register_visualization_tools() -> None:
    """Register all visualization tools. Called automatically on import."""
    pass


__all__ = [
    "scatter_plot",
    "bar_chart",
    "line_chart",
    "histogram",
    "box_plot",
    "violin_plot",
    "heatmap",
    "pie_chart",
    "VISUALIZATION_TOOLS",
    "register_visualization_tools",
]
