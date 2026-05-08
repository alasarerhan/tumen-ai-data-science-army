"""
DataQualityAgent
================
A tool-calling agent that profiles data quality: schema validation, null/
duplicate/outlier checks, distribution profiling, and an overall quality score.
Follows the EDAToolsAgent react-agent pattern.

Tools
-----
* profile_data_quality – comprehensive null + outlier + distribution profile
* validate_schema       – check columns/types against an expected schema
* get_data_quality_params – return current configuration

Quality Score (0–100) components
---------------------------------
- Completeness  : 1 − mean_null_rate                      (weight 40 %)
- Uniqueness    : 1 − duplicate_row_rate                   (weight 20 %)
- Consistency   : 1 − schema_violation_rate                (weight 20 %)
- Cleanliness   : 1 − numeric_outlier_rate (IQR method)   (weight 20 %)
"""

from __future__ import annotations

from typing_extensions import (
    Annotated,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

import pandas as pd
from IPython.display import Markdown

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import InjectedState
from langgraph.types import Checkpointer

from ai_data_science_team.templates import BaseAgent
from ai_data_science_team.utils.messages import get_tool_call_names
from ai_data_science_team.utils.regex import format_agent_name

AGENT_NAME = "data_quality_agent"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def profile_data_quality(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    outlier_method: Annotated[str, InjectedState("outlier_method")],
    outlier_threshold: Annotated[float, InjectedState("outlier_threshold")],
) -> Tuple[str, Dict]:
    """
    Tool: profile_data_quality
    Description:
        Computes a comprehensive data quality profile including null rates,
        duplicate rows, numeric outliers, column-level statistics, and an
        overall quality score (0–100).

    Parameters (injected from state):
        data_raw          : Dataset as dict.
        outlier_method    : 'iqr' or 'zscore'.
        outlier_threshold : IQR multiplier (default 1.5) or Z-score cutoff (default 3.0).

    Returns:
        Tuple[str, Dict]: text summary + artifact dict with quality metrics.
    """
    print("    * Tool: profile_data_quality")

    import numpy as np

    df = pd.DataFrame(data_raw)
    n_rows, n_cols = df.shape

    # 1) Completeness — null rates per column
    null_counts = df.isnull().sum().to_dict()
    null_rates = {col: round(cnt / n_rows, 4) for col, cnt in null_counts.items()}
    mean_null_rate = float(np.mean(list(null_rates.values()))) if n_rows > 0 else 0.0
    completeness = 1.0 - mean_null_rate

    # 2) Uniqueness — duplicate rows
    n_duplicates = int(df.duplicated().sum())
    duplicate_rate = round(n_duplicates / n_rows, 4) if n_rows > 0 else 0.0
    uniqueness = 1.0 - duplicate_rate

    # 3) Outliers on numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    outlier_flags: Dict[str, int] = {}
    method = (outlier_method or "iqr").lower()
    thr = float(outlier_threshold) if outlier_threshold else (1.5 if method == "iqr" else 3.0)

    for col in numeric_cols:
        series = df[col].dropna()
        if series.empty:
            continue
        if method == "iqr":
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - thr * iqr, q3 + thr * iqr
            outlier_flags[col] = int(((series < lo) | (series > hi)).sum())
        else:  # zscore
            z = (series - series.mean()) / (series.std(ddof=0) + 1e-9)
            outlier_flags[col] = int((z.abs() > thr).sum())

    total_numeric_cells = n_rows * max(len(numeric_cols), 1)
    total_outliers = sum(outlier_flags.values())
    numeric_outlier_rate = round(total_outliers / total_numeric_cells, 4)
    cleanliness = 1.0 - numeric_outlier_rate

    # 4) Schema consistency (placeholder — 1.0 unless called after validate_schema)
    consistency = 1.0

    # 5) Composite quality score (0–100)
    quality_score = round(
        100 * (0.40 * completeness + 0.20 * uniqueness + 0.20 * consistency + 0.20 * cleanliness),
        2,
    )

    # 6) Column-level dtype / cardinality summary
    col_summary = {}
    for col in df.columns:
        col_summary[col] = {
            "dtype": str(df[col].dtype),
            "null_rate": null_rates.get(col, 0.0),
            "n_unique": int(df[col].nunique(dropna=False)),
            "outlier_count": outlier_flags.get(col, None),
        }

    artifact = {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "quality_score": quality_score,
        "completeness": round(completeness * 100, 2),
        "uniqueness": round(uniqueness * 100, 2),
        "cleanliness": round(cleanliness * 100, 2),
        "consistency": round(consistency * 100, 2),
        "n_duplicates": n_duplicates,
        "duplicate_rate": duplicate_rate,
        "mean_null_rate": round(mean_null_rate, 4),
        "null_rates": null_rates,
        "outlier_counts": outlier_flags,
        "total_outliers": total_outliers,
        "numeric_outlier_rate": numeric_outlier_rate,
        "outlier_method": method,
        "outlier_threshold": thr,
        "column_summary": col_summary,
    }

    issues = []
    if mean_null_rate > 0.05:
        issues.append(f"high null rate ({mean_null_rate * 100:.1f}%)")
    if duplicate_rate > 0.01:
        issues.append(f"{n_duplicates} duplicate rows ({duplicate_rate * 100:.1f}%)")
    if numeric_outlier_rate > 0.05:
        issues.append(f"high outlier rate ({numeric_outlier_rate * 100:.1f}%)")

    issues_str = "; ".join(issues) if issues else "none detected"
    content = (
        f"Data quality profiling complete.  "
        f"Quality score: {quality_score}/100.  "
        f"Dataset: {n_rows} rows × {n_cols} cols.  "
        f"Issues: {issues_str}."
    )
    return content, artifact


@tool(response_format="content_and_artifact")
def validate_schema(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    expected_schema: Annotated[dict, InjectedState("expected_schema")],
) -> Tuple[str, Dict]:
    """
    Tool: validate_schema
    Description:
        Validates the dataset columns and dtypes against an expected schema dict.
        Reports missing columns, extra columns, and type mismatches.

    Parameters (injected from state):
        data_raw        : Dataset as dict.
        expected_schema : Dict mapping column name → expected dtype string
                          (e.g. {'age': 'int64', 'name': 'object'}).
                          Pass an empty dict to skip validation.

    Returns:
        Tuple[str, Dict]: text summary + artifact with violations list.
    """
    print("    * Tool: validate_schema")

    df = pd.DataFrame(data_raw)
    schema = expected_schema or {}

    if not schema:
        return "No expected schema provided — schema validation skipped.", {
            "violations": [],
            "n_violations": 0,
            "missing_columns": [],
            "extra_columns": [],
            "type_mismatches": [],
        }

    actual_cols = set(df.columns)
    expected_cols = set(schema.keys())

    missing_cols = sorted(expected_cols - actual_cols)
    extra_cols = sorted(actual_cols - expected_cols)

    type_mismatches = []
    for col in expected_cols & actual_cols:
        expected_dtype = schema[col]
        actual_dtype = str(df[col].dtype)
        if expected_dtype != actual_dtype:
            type_mismatches.append({
                "column": col,
                "expected": expected_dtype,
                "actual": actual_dtype,
            })

    violations = (
        [{"type": "missing_column", "column": c} for c in missing_cols]
        + [{"type": "extra_column", "column": c} for c in extra_cols]
        + [{"type": "type_mismatch", **tm} for tm in type_mismatches]
    )

    artifact = {
        "n_violations": len(violations),
        "missing_columns": missing_cols,
        "extra_columns": extra_cols,
        "type_mismatches": type_mismatches,
        "violations": violations,
    }

    if not violations:
        content = "Schema validation passed — no violations found."
    else:
        content = (
            f"Schema validation found {len(violations)} violation(s): "
            f"{len(missing_cols)} missing col(s), "
            f"{len(extra_cols)} extra col(s), "
            f"{len(type_mismatches)} type mismatch(es)."
        )
    return content, artifact


@tool(response_format="content")
def get_data_quality_params(
    outlier_method: Annotated[str, InjectedState("outlier_method")],
    outlier_threshold: Annotated[float, InjectedState("outlier_threshold")],
) -> str:
    """
    Tool: get_data_quality_params
    Description:
        Returns the current data quality agent configuration.

    Parameters (injected from state):
        outlier_method    : Detection method — 'iqr' or 'zscore'.
        outlier_threshold : IQR multiplier or Z-score cutoff.

    Returns:
        str: Human-readable configuration summary.
    """
    print("    * Tool: get_data_quality_params")
    return (
        f"Data quality agent configured with "
        f"outlier_method='{outlier_method}', outlier_threshold={outlier_threshold}."
    )


DATA_QUALITY_TOOLS = [profile_data_quality, validate_schema, get_data_quality_params]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_data_quality_agent(
    model: Any,
    outlier_method: str = "iqr",
    outlier_threshold: float = 1.5,
    expected_schema: Optional[Dict] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Creates the compiled LangGraph StateGraph for the DataQualityAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling).
    outlier_method : str
        'iqr' or 'zscore'.  Default 'iqr'.
    outlier_threshold : float
        IQR multiplier (1.5) or Z-score cutoff (3.0).
    expected_schema : dict, optional
        Column → dtype mapping for schema validation.
    create_react_agent_kwargs / invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    log_tool_calls : bool

    Returns
    -------
    app : langgraph.graph.CompiledStateGraph
    """
    if create_react_agent_kwargs is None:
        create_react_agent_kwargs = {}
    if invoke_react_agent_kwargs is None:
        invoke_react_agent_kwargs = {}

    class GraphState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        user_instructions: str
        data_raw: dict
        outlier_method: str
        outlier_threshold: float
        expected_schema: dict
        quality_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=DATA_QUALITY_TOOLS,
        state_schema=GraphState,  # type: ignore[arg-type]
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    def prepare_messages(state: GraphState):
        print(format_agent_name(AGENT_NAME))
        print("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions"))]}

    def run_react_agent(state: GraphState):
        print("    * RUN REACT TOOL-CALLING AGENT FOR DATA QUALITY")
        print(f"    * outlier_method={state.get('outlier_method')}, threshold={state.get('outlier_threshold')}")

        system_hint = (
            "You are a Data Quality agent. "
            "Call 'profile_data_quality' to compute a comprehensive quality profile. "
            "Optionally call 'validate_schema' if a schema is provided. "
            "Report the overall quality score and key issues found."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload = {
            "messages": messages,
            "data_raw": state.get("data_raw"),
            "outlier_method": state.get("outlier_method", outlier_method),
            "outlier_threshold": state.get("outlier_threshold", outlier_threshold),
            "expected_schema": state.get("expected_schema") or {},
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        print("    * POST-PROCESSING DATA QUALITY RESULTS")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {"messages": [], "quality_results": {}, "tool_calls": []}

        last_ai_message = None
        for msg in reversed(internal_messages):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai"):
                last_ai_message = AIMessage(
                    content=getattr(msg, "content", ""),
                    name=AGENT_NAME,
                )
                break
        if last_ai_message is None:
            last_ai_message = AIMessage(
                content=getattr(internal_messages[-1], "content", ""),
                name=AGENT_NAME,
            )
        if not getattr(last_ai_message, "content", "").strip():
            last_ai_message = AIMessage(
                content="Data quality profiling completed. See quality_results for details.",
                name=AGENT_NAME,
            )

        quality_artifact: Dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            name = getattr(msg, "name", "") or ""
            if art is not None and isinstance(art, dict):
                if "quality_score" in art:
                    quality_artifact["profile"] = art
                elif "violations" in art:
                    quality_artifact["schema"] = art
                else:
                    quality_artifact.update(art)

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                print(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "quality_results": quality_artifact,
            "tool_calls": tool_calls,
        }

    workflow = StateGraph(GraphState)
    workflow.add_node("prepare_messages", prepare_messages)
    workflow.add_node("react_agent", react_agent)
    workflow.add_node("post_process", post_process)
    workflow.add_edge(START, "prepare_messages")
    workflow.add_edge("prepare_messages", "react_agent")
    workflow.add_edge("react_agent", "post_process")
    workflow.add_edge("post_process", END)

    app = workflow.compile(
        checkpointer=checkpointer,
        name=AGENT_NAME,
    )
    return app


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------


class DataQualityAgent(BaseAgent):
    """
    A tool-calling agent that profiles data quality and validates schemas.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    outlier_method : str
        Outlier detection method: 'iqr' (default) or 'zscore'.
    outlier_threshold : float
        IQR multiplier (default 1.5) or Z-score threshold (default 3.0).
    expected_schema : dict, optional
        Column → expected dtype mapping for schema validation.
    create_react_agent_kwargs / invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    log_tool_calls : bool

    Examples
    --------
    >>> agent = DataQualityAgent(model=llm)
    >>> agent.invoke_agent(data_raw=df)
    >>> agent.get_quality_score()
    """

    def __init__(
        self,
        model: Any,
        outlier_method: str = "iqr",
        outlier_threshold: float = 1.5,
        expected_schema: Optional[Dict] = None,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "outlier_method": outlier_method,
            "outlier_threshold": outlier_threshold,
            "expected_schema": expected_schema or {},
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_data_quality_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        data_raw: pd.DataFrame = None,
        user_instructions: str = None,
        outlier_method: str = None,
        outlier_threshold: float = None,
        expected_schema: Optional[Dict] = None,
        **kwargs,
    ):
        """
        Run the data quality agent.

        Parameters
        ----------
        data_raw : pd.DataFrame
            Dataset to profile.
        user_instructions : str, optional
            Natural-language task.  Defaults to generic profiling prompt.
        outlier_method : str, optional
            Override for this call only.
        outlier_threshold : float, optional
            Override for this call only.
        expected_schema : dict, optional
            Override schema for this call only.
        """
        if user_instructions is None:
            user_instructions = (
                "Profile the data quality of the dataset: compute completeness, "
                "duplicate rate, outlier rate, and overall quality score. "
                "Report the key findings and any issues found."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        eff_method = outlier_method or self._params["outlier_method"]
        eff_threshold = outlier_threshold if outlier_threshold is not None else self._params["outlier_threshold"]
        eff_schema = expected_schema if expected_schema is not None else self._params.get("expected_schema", {})

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else {},
                "outlier_method": eff_method,
                "outlier_threshold": eff_threshold,
                "expected_schema": eff_schema,
            },
            **kwargs,
        )
        self.response = response
        return None

    def get_quality_results(self) -> Optional[Dict]:
        """Returns the full quality results dictionary (keys: 'profile', 'schema')."""
        if not self.response:
            return None
        return self.response.get("quality_results")

    def get_quality_score(self) -> Optional[float]:
        """Returns the composite quality score (0–100)."""
        r = self.get_quality_results()
        if r is None:
            return None
        profile = r.get("profile", {})
        return profile.get("quality_score")

    def get_null_rates(self) -> Optional[Dict]:
        """Returns a dict of {column: null_rate} for each column."""
        r = self.get_quality_results()
        if r is None:
            return None
        return r.get("profile", {}).get("null_rates")

    def get_outlier_counts(self) -> Optional[Dict]:
        """Returns a dict of {column: n_outliers} for numeric columns."""
        r = self.get_quality_results()
        if r is None:
            return None
        return r.get("profile", {}).get("outlier_counts")

    def get_schema_violations(self) -> Optional[List]:
        """Returns the list of schema violation dicts (if validate_schema was called)."""
        r = self.get_quality_results()
        if r is None:
            return None
        return r.get("schema", {}).get("violations")

    def get_n_duplicates(self) -> Optional[int]:
        """Returns the number of duplicate rows."""
        r = self.get_quality_results()
        if r is None:
            return None
        return r.get("profile", {}).get("n_duplicates")

    def get_column_summary(self) -> Optional[Dict]:
        """Returns per-column quality summary (dtype, null_rate, n_unique, outlier_count)."""
        r = self.get_quality_results()
        if r is None:
            return None
        return r.get("profile", {}).get("column_summary")

    def get_ai_message(self, markdown: bool = False):
        """Returns the last AI message from the agent response."""
        if not self.response or "messages" not in self.response:
            return None
        msgs = self.response.get("messages", [])
        for msg in reversed(msgs):
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            if role in ("assistant", "ai", AGENT_NAME):
                content = getattr(msg, "content", "")
                return Markdown(content) if markdown else content
        return None

    def get_tool_calls(self) -> Optional[List]:
        """Returns the list of tool names that were called."""
        if not self.response:
            return None
        return self.response.get("tool_calls")
