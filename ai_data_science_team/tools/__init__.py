"""AI Data Science Team Tools.

This package provides a comprehensive set of tools for data science workflows.
All tools are registered in the central ToolRegistry for dynamic discovery.

Usage
-----
::

    from ai_data_science_team.tools import register_all_tools
    from ai_data_science_team.tool_registry import ToolRegistry

    # Register all tools
    register_all_tools()

    # Search for tools
    tools = ToolRegistry.search(capability="visualization")

    # Get a tool
    tool_def, executor = ToolRegistry.get("scatter_plot")

Namespaces
----------
- core.visualization: Chart and plotting tools
- core.profiling: Data profiling and analysis tools
- core.database: Database introspection and query tools
- core.wrangling: Data transformation and manipulation tools
- core.cleaning: Data cleaning and preprocessing tools
- core.anomaly: Anomaly detection algorithms
- core.feature_engineering: Feature engineering operations
- core.model: Model loading, inference, and evaluation
"""

from __future__ import annotations

from ai_data_science_team.tool_registry import ToolRegistry


def register_all_tools() -> None:
    """Register all available tools in the ToolRegistry.

    This function imports all tool modules, which automatically registers
    them via the @register_tool decorator.
    """
    from ai_data_science_team.tools.visualization import VISUALIZATION_TOOLS
    from ai_data_science_team.tools.profiling import PROFILING_TOOLS
    from ai_data_science_team.tools.database import DATABASE_TOOLS
    from ai_data_science_team.tools.wrangling import WRANGLING_TOOLS
    from ai_data_science_team.tools.cleaning import CLEANING_TOOLS
    from ai_data_science_team.tools.anomaly import ANOMALY_TOOLS
    from ai_data_science_team.tools.feature_engineering import FEATURE_ENGINEERING_TOOLS
    from ai_data_science_team.tools.model import MODEL_TOOLS


register_all_tools()


VISUALIZATION_TOOLS = [
    "scatter_plot", "bar_chart", "line_chart", "histogram",
    "box_plot", "violin_plot", "heatmap", "pie_chart"
]
PROFILING_TOOLS = [
    "profile_dataframe", "infer_units", "resolve_column_aliases", "format_profile_for_prompt"
]
DATABASE_TOOLS = [
    "introspect_schema", "sample_table", "execute_sql", "validate_sql_safety"
]
WRANGLING_TOOLS = [
    "filter_rows", "select_columns", "rename_columns", "aggregate_data",
    "merge_datasets", "pivot_data", "transform_column"
]
CLEANING_TOOLS = [
    "remove_missing_columns", "impute_missing", "remove_duplicates",
    "remove_outliers", "convert_types"
]
ANOMALY_TOOLS = [
    "isolation_forest_detect", "lof_detect", "hbos_detect",
    "copod_detect", "ensemble_detect"
]
FEATURE_ENGINEERING_TOOLS = [
    "one_hot_encode", "label_encode", "create_datetime_features",
    "scale_features", "create_polynomial_features", "bin_numeric", "select_features"
]
MODEL_TOOLS = [
    "load_model", "predict_classification", "predict_regression", "evaluate_model"
]

ALL_TOOLS = (
    VISUALIZATION_TOOLS +
    PROFILING_TOOLS +
    DATABASE_TOOLS +
    WRANGLING_TOOLS +
    CLEANING_TOOLS +
    ANOMALY_TOOLS +
    FEATURE_ENGINEERING_TOOLS +
    MODEL_TOOLS
)


__all__ = [
    "register_all_tools",
    "ToolRegistry",
    "VISUALIZATION_TOOLS",
    "PROFILING_TOOLS",
    "DATABASE_TOOLS",
    "WRANGLING_TOOLS",
    "CLEANING_TOOLS",
    "ANOMALY_TOOLS",
    "FEATURE_ENGINEERING_TOOLS",
    "MODEL_TOOLS",
    "ALL_TOOLS",
]
