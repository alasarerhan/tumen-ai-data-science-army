import logging

from typing_extensions import Annotated, Dict, Tuple, Union

logger = logging.getLogger(__name__)
import os  # noqa: E402, F401
import tempfile  # noqa: E402, F401
import warnings  # noqa: E402, F401

from langchain.tools import tool  # noqa: E402, F401
from langgraph.prebuilt import InjectedState  # noqa: E402, F401

from ai_data_science_team.tools.dataframe import get_dataframe_summary  # noqa: E402, F401


def _pytimetk_fallback_binarize(
    df, n_bins: int = 4, thresh_infreq: float = 0.01, name_infreq: str = "-OTHER"
):
    """Pure-pandas binarizer used when pytimetk is unavailable (e.g. py3.13).

    Numeric columns → quantile-binned one-hot (col__bin_{i}); categorical
    columns → per-level one-hot (col__<value>). Infrequent levels (below
    ``thresh_infreq``) collapse to ``name_infreq`` to match pytimetk semantics.
    """
    import pandas as pd

    out = pd.DataFrame(index=df.index)
    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 1:
            try:
                bins = pd.qcut(s.rank(method="first"), q=n_bins, labels=False, duplicates="drop")
            except ValueError:
                # Too few unique values for qcut
                bins = pd.cut(
                    s,
                    bins=min(n_bins, s.nunique(dropna=True) or 1),
                    labels=False,
                    include_lowest=True,
                )
            for i in sorted(bins.dropna().unique()):
                out[f"{c}__bin_{int(i)}"] = (bins == i).astype(int)
        else:
            counts = s.value_counts(dropna=True, normalize=True)
            rare = set(counts[counts < thresh_infreq].index)
            s2 = s.where(~s.isin(rare), name_infreq)
            for v in sorted(s2.dropna().unique(), key=lambda x: str(x)):
                col_name = f"{c}__{v}".replace(" ", "_")
                out[col_name] = (s2 == v).astype(int)
    return out


@tool(response_format="content")
def explain_data(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    n_sample: int = 30,
    skip_stats: bool = False,
):
    """
    Tool: explain_data
    Description:
        Provides an extensive, narrative summary of a DataFrame including its shape, column types,
        missing value percentages, unique counts, sample rows, and (if not skipped) descriptive stats/info.

    Parameters:
        data_raw (dict): Raw data.
        n_sample (int, default=30): Number of rows to display.
        skip_stats (bool, default=False): If True, omit descriptive stats/info.

    LLM Guidance:
        Use when a detailed, human-readable explanation is needed—i.e., a full overview is preferred over a concise numerical summary.

    Returns:
        str: Detailed DataFrame summary.
    """
    logger.info("    * Tool: explain_data")
    import pandas as pd  # noqa: E402, F401

    result = get_dataframe_summary(pd.DataFrame(data_raw), n_sample=n_sample, skip_stats=skip_stats)

    return result


@tool(response_format="content_and_artifact")
def describe_dataset(
    data_raw: Annotated[dict, InjectedState("data_raw")],
) -> Tuple[str, Dict]:
    """
    Tool: describe_dataset
    Description:
        Compute and return summary statistics for the dataset using pandas' describe() method.
        The tool provides both a textual summary and a structured artifact (a dictionary) for further processing.

    Parameters:
    -----------
    data_raw : dict
        The raw data in dictionary format.

    LLM Selection Guidance:
    ------------------------
    Use this tool when:
      - The request emphasizes numerical descriptive statistics (e.g., count, mean, std, min, quartiles, max).
      - The user needs a concise statistical snapshot rather than a detailed narrative.
      - Both a brief text explanation and a structured data artifact (for downstream tasks) are required.

    Returns:
    -------
    Tuple[str, Dict]:
        - content: A textual summary indicating that summary statistics have been computed.
        - artifact: A dictionary (derived from DataFrame.describe()) containing detailed statistical measures.
    """
    logger.info("    * Tool: describe_dataset")
    import pandas as pd  # noqa: E402, F401

    df = pd.DataFrame(data_raw)
    description_df = df.describe(include="all")
    content = "Summary statistics computed using pandas describe()."
    # Flatten: orient="index" gives rows=stat, columns=columns
    flattened = description_df.reset_index().rename(columns={"index": "stat"})
    artifact = {"describe_df": flattened.to_dict(orient="list")}
    return content, artifact


@tool(response_format="content_and_artifact")
def visualize_missing(
    data_raw: Annotated[dict, InjectedState("data_raw")], n_sample: int = None
) -> Tuple[str, Dict]:
    """
    Tool: visualize_missing
    Description:
        Missing value analysis using the missingno library. Generates a matrix plot, bar plot, and heatmap plot.

    Parameters:
    -----------
    data_raw : dict
        The raw data in dictionary format.
    n_sample : int, optional (default: None)
        The number of rows to sample from the dataset if it is large.

    Returns:
    -------
    Tuple[str, Dict]:
        content: A message describing the generated plots.
        artifact: A dict with keys 'matrix_plot', 'bar_plot', and 'heatmap_plot' each containing the
                  corresponding base64 encoded PNG image.
    """
    logger.info("    * Tool: visualize_missing")

    try:
        import missingno as msno  # Ensure missingno is installed  # noqa: E402, F401
    except ImportError:
        raise ImportError(
            "Please install the 'missingno' package to use this tool. pip install missingno"
        )

    import base64  # noqa: E402, F401
    from io import BytesIO  # noqa: E402, F401

    import matplotlib.pyplot as plt  # noqa: E402, F401
    import pandas as pd  # noqa: E402, F401

    # Create the DataFrame and sample if n_sample is provided.
    df = pd.DataFrame(data_raw)
    if n_sample is not None:
        # Clamp to population size — missingno internally also samples, and
        # df.sample(n=k, replace=False) raises when k > len(df).
        n_sample = max(1, min(int(n_sample), len(df)))
        df = df.sample(n=n_sample, random_state=42)

    # Dictionary to store the base64 encoded images for each plot.
    encoded_plots = {}

    # Define a helper function to create a plot, save it, and encode it.
    def create_and_encode_plot(plot_func):
        plt.figure(figsize=(8, 6))
        # Call the missingno plotting function.
        plot_func(df)
        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # Create and encode the matrix plot.
    encoded_plots["matrix_plot"] = create_and_encode_plot(msno.matrix)

    # Create and encode the bar plot.
    encoded_plots["bar_plot"] = create_and_encode_plot(msno.bar)

    # Create and encode the heatmap plot.
    encoded_plots["heatmap_plot"] = create_and_encode_plot(msno.heatmap)

    content = "Missing data visualizations (matrix, bar, and heatmap) have been generated."
    artifact = encoded_plots
    return content, artifact


@tool(response_format="content_and_artifact")
def generate_correlation_funnel(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    target: str,
    target_bin_index: Union[int, str] = -1,
    corr_method: str = "pearson",
    n_bins: int = 4,
    thresh_infreq: float = 0.01,
    name_infreq: str = "-OTHER",
) -> Tuple[str, Dict]:
    """
    Tool: generate_correlation_funnel
    Description:
        Correlation analysis using the correlation funnel method. The tool binarizes the data and computes correlation versus a target column.

    Parameters:
    ----------
    target : str
        The base target column name (e.g., 'Member_Status'). The tool will look for columns that begin
        with this string followed by '__' (e.g., 'Member_Status__Gold', 'Member_Status__Platinum').
    target_bin_index : int or str, default -1
        If an integer, selects the target level by position from the matching columns.
        If a string (e.g., "Yes"), attempts to match to the suffix of a column name
        (i.e., 'target__Yes').
    corr_method : str
        The correlation method ('pearson', 'kendall', or 'spearman'). Default is 'pearson'.
    n_bins : int
        The number of bins to use for binarization. Default is 4.
    thresh_infreq : float
        The threshold for infrequent levels. Default is 0.01.
    name_infreq : str
        The name to use for infrequent levels. Default is '-OTHER'.
    """
    logger.info("    * Tool: generate_correlation_funnel")
    # pytimetk is optional — py3.13 + numpy>=2 has no wheel. If installed, prefer it
    # (more accurate binning via tk.binarize); otherwise fall back to a pure
    # pandas+plotly implementation that works on any supported Python.
    import base64  # noqa: E402, F401
    import json  # noqa: E402, F401
    from io import BytesIO  # noqa: E402, F401

    import matplotlib.pyplot as plt  # noqa: E402, F401
    import pandas as pd  # noqa: F402, F401
    import plotly.io as pio  # noqa: E402, F401

    try:
        import pytimetk as tk  # noqa: F401

        _HAS_PYTIMETK = True
    except ImportError:
        _HAS_PYTIMETK = False

    # Convert the raw injected state into a DataFrame.
    df = pd.DataFrame(data_raw)

    if _HAS_PYTIMETK:
        # pytimetk path — full functionality (binarize, correlate, plot)
        df_binarized = df.binarize(
            n_bins=n_bins,
            thresh_infreq=thresh_infreq,
            name_infreq=name_infreq,
            one_hot=True,
        )
        matching_columns = [c for c in df_binarized.columns if c.startswith(f"{target}__")]
        if not matching_columns:
            full_target = target
        else:
            if isinstance(target_bin_index, str):
                candidate = f"{target}__{target_bin_index}"
                full_target = candidate if candidate in matching_columns else matching_columns[-1]
            else:
                try:
                    full_target = matching_columns[target_bin_index]
                except IndexError:
                    full_target = matching_columns[-1]
        df_correlated = df_binarized.correlate(target=full_target, method=corr_method)
    else:
        # Fallback: pure pandas binarization (quantile for numerics, one-hot for categoricals)
        # + Pearson correlation with the target.
        df_binarized = _pytimetk_fallback_binarize(
            df, n_bins=n_bins, thresh_infreq=thresh_infreq, name_infreq=name_infreq
        )
        # Pick a target binarization column. Strategy:
        #  - If target appears in binarized columns directly (numeric target was kept as-is
        #    by fallback because it had too few unique values, or it was a one-hot column),
        #    use the highest-correlated matching target.
        #  - Otherwise fall back to the first column matching the target prefix.
        if target in df_binarized.columns:
            full_target = target
        else:
            matching = [c for c in df_binarized.columns if c.startswith(f"{target}__")]
            if matching:
                # use target_bin_index or the last
                if isinstance(target_bin_index, str):
                    cand = f"{target}__{target_bin_index}"
                    full_target = cand if cand in matching else matching[-1]
                else:
                    try:
                        full_target = matching[target_bin_index]
                    except IndexError:
                        full_target = matching[-1]
            else:
                # No matching binarized column. The target might be numeric
                # and got quantile-binned; correlate against the first bin
                # and the merged result will still be useful.
                fallback_cols = [c for c in df_binarized.columns if c.startswith(f"{target}__bin_")]
                if fallback_cols:
                    full_target = fallback_cols[-1]
                else:
                    raise ValueError(
                        f"target={target!r} not found after binarization. "
                        f"Available: {list(df_binarized.columns)[:10]}..."
                    )
        corr = df_binarized.corr(method=corr_method).get(full_target, pd.Series(dtype=float))
        df_correlated = corr.dropna().sort_values(ascending=False).rename("correlation").to_frame()

    # Attempt to generate a static plot.
    # Normalize df_correlated: accept either a pytimetk DataFrame or our
    # fallback Series-to-DataFrame ("correlation" col, index = feature name).
    if "correlation" in df_correlated.columns and df_correlated.shape[1] == 1:
        corr_series = df_correlated["correlation"].dropna().sort_values(ascending=False)
    else:
        # pytimetk: contains feature + correlation cols
        feature_col = (
            df_correlated.columns[0]
            if df_correlated.columns[0] not in ("feature", "variable")
            else None
        )
        if feature_col is None:
            # heuristic: correlation-like column
            num_cols = [c for c in df_correlated.columns if df_correlated[c].dtype.kind in "fiub"]
            corr_series = (
                df_correlated.set_index(feature_col or df_correlated.columns[0])[num_cols[-1]]
                .dropna()
                .sort_values(ascending=False)
            )
        else:
            num_cols = [
                c
                for c in df_correlated.columns
                if c != feature_col and df_correlated[c].dtype.kind in "fiub"
            ]
            corr_series = (
                df_correlated.set_index(feature_col)[num_cols[0]]
                .dropna()
                .sort_values(ascending=False)
            )
    encoded: Union[str, Dict] = ""
    try:
        # matplotlib horizontal bar — works for both formats
        fig, ax = plt.subplots(figsize=(8, max(4, 0.3 * len(corr_series))))
        corr_series.head(20).plot(kind="barh", ax=ax)
        ax.invert_yaxis()
        ax.set_xlabel("Correlation")
        ax.set_title("Correlation funnel")
        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        buf.seek(0)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        encoded = {"error": str(e)}

    # Attempt to generate a Plotly plot.
    fig_dict = None
    try:
        import plotly.graph_objects as go

        top = corr_series.head(20)
        fig = go.Figure(go.Bar(x=top.values, y=top.index, orientation="h"))
        fig.update_layout(
            title="Correlation funnel",
            xaxis_title="Correlation",
            yaxis=dict(autorange="reversed"),
        )
        fig_json = pio.to_json(fig)
        fig_dict = json.loads(fig_json)
    except Exception as e:
        fig_dict = {"error": str(e)}

    content = (
        f"Correlation funnel computed using method '{corr_method}' for target level '{full_target}'. "
        f"Base target was '{target}' with target_bin_index '{target_bin_index}'."
    )
    artifact = {
        "correlation_data": df_correlated.to_dict(orient="list"),
        "plot_image": encoded,
        "plotly_figure": fig_dict,
    }
    return content, artifact


@tool(response_format="content_and_artifact")
def generate_sweetviz_report(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    target: str = None,
    report_name: str = "sweetviz_report.html",
    report_directory: str = None,  # <-- Default to None
    open_browser: bool = False,
    include_html: bool = False,
) -> Tuple[str, Dict]:
    """
    Tool: generate_sweetviz_report
    Description:
        Make an Exploratory Data Analysis (EDA) report using the Sweetviz library.

    Parameters:
    -----------
    data_raw : dict
        The raw data injected as a dictionary (converted from a DataFrame).
    target : str, optional
        The target feature to analyze. Default is None.
    report_name : str, optional
        The file name to save the Sweetviz HTML report. Default is "sweetviz_report.html".
    report_directory : str, optional
        The directory where the report should be saved.
        If None, a unique subdirectory under `pipeline_reports/` is created and used.
    open_browser : bool, optional
        Whether to open the report in a web browser. Default is False.
    include_html : bool, optional
        If True, includes the full HTML content in the returned artifact. Default is False.

    Returns:
    --------
    Tuple[str, Dict]:
        content: A summary message describing the generated report.
        artifact: A dictionary with the report file path and optionally the report's HTML content.
    """
    logger.info("    * Tool: generate_sweetviz_report")

    # Import sweetviz
    try:
        import sweetviz as sv  # noqa: E402, F401
    except ImportError:
        raise ImportError(
            "Please install the 'sweetviz' package to use this tool. Run: pip install sweetviz"
        )

    import pandas as pd  # noqa: E402, F401

    # Convert injected raw data to a DataFrame.
    df = pd.DataFrame(data_raw)

    # Sweetviz (2.3.x) internally calls pd.melt(value_name="value"); any user
    # column literally named "value" (e.g. our sample fixture) collides and
    # raises ValueError. Rename the literal to avoid the collision.
    rename_map = {c: f"col_{i}" for i, c in enumerate(df.columns) if c == "value"}
    if rename_map:
        df = df.rename(columns=rename_map)
        if target == "value":
            target = "col_0"
        logger.info("    * Renamed 'value' columns to avoid Sweetviz pd.melt collision")

    # If no directory is specified, use a temporary directory.
    if not report_directory:
        base_reports_dir = os.path.abspath(os.path.join(os.getcwd(), "pipeline_reports"))
        os.makedirs(base_reports_dir, exist_ok=True)
        report_directory = tempfile.mkdtemp(prefix="sweetviz_", dir=base_reports_dir)
        logger.info(f"    * Using pipeline reports directory: {report_directory}")
    else:
        # Ensure user-specified directory exists.
        if not os.path.exists(report_directory):
            os.makedirs(report_directory)

    # Create the Sweetviz report.
    # Sweetviz internally calls warnings.filterwarnings on np.VisibleDeprecationWarning; this is removed in numpy>=2.
    import numpy as np  # noqa: E402, F401

    # NumPy >= 2 removed VisibleDeprecationWarning; Sweetviz still references it directly.
    if not hasattr(np, "VisibleDeprecationWarning"):
        # Provide a compatible placeholder to avoid AttributeError inside Sweetviz.
        np.VisibleDeprecationWarning = DeprecationWarning  # type: ignore[attr-defined]

    visible_dep = getattr(np, "VisibleDeprecationWarning", DeprecationWarning)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=visible_dep)
        report = sv.analyze(df, target_feat=target)

    # Determine the full path for the report.
    full_report_path = os.path.join(report_directory, report_name)

    # Save the report to the specified HTML file.
    report.show_html(
        filepath=full_report_path,
        open_browser=open_browser,
    )

    html_content = None
    if include_html:
        try:
            with open(full_report_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception:
            html_content = None

    content = (
        f"Sweetviz EDA report generated and saved as '{os.path.abspath(full_report_path)}'. "
        f"{'This was saved under pipeline_reports.' if 'pipeline_reports' in report_directory else ''}"
    )
    artifact = {
        "report_file": os.path.abspath(full_report_path),
        "report_html": html_content,
    }
    return content, artifact


@tool(response_format="content_and_artifact")
def generate_dtale_report(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    host: str = "localhost",
    port: int = 40000,
    open_browser: bool = False,
) -> Tuple[str, Dict]:
    """
    Tool: generate_dtale_report
    Description:
        Creates an interactive data exploration report using the dtale library.

    Parameters:
    -----------
    data_raw : dict
        The raw data in dictionary format.
    host : str, optional
        The host IP address to serve the dtale app. Default is "localhost".
    port : int, optional
        The port number to serve the dtale app. Default is 40000.
    open_browser : bool, optional
        Whether to open the report in a web browser. Default is False.

    Returns:
    --------
    Tuple[str, Dict]:
        content: A summary message describing the dtale report.
        artifact: A dictionary containing the URL of the dtale report.
    """
    logger.info("    * Tool: generate_dtale_report")

    try:
        import dtale  # noqa: E402, F401
    except ImportError:
        raise ImportError(
            "Please install the 'dtale' package to use this tool. Run: pip install dtale"
        )

    import pandas as pd  # noqa: E402, F401

    df = pd.DataFrame(data_raw)

    # Create the dtale report
    d = dtale.show(df, host=host, port=port, open_browser=open_browser)

    content = f"Dtale report generated and available at: {d.main_url()}"
    artifact = {"dtale_url": d.main_url()}

    return content, artifact
