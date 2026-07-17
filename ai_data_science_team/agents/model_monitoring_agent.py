from __future__ import annotations

"""
ModelMonitoringAgent
====================
A tool-calling agent that monitors ML model health in production: detects
feature/prediction distribution drift (PSI + KS test) and measures
model performance degradation against a baseline.
Follows the EDAToolsAgent react-agent pattern.

Tools
-----
* detect_drift          – PSI + KS-test drift on reference vs current data
* compute_performance   – compute classification/regression metrics
* get_monitoring_params – return current configuration

Drift severity thresholds (PSI)
---------------------------------
- PSI < 0.1   : no significant drift (stable)
- 0.1–0.25    : moderate drift (monitor closely)
- PSI > 0.25  : significant drift (action required)
"""

import logging  # noqa: E402, F401

logger = logging.getLogger(__name__)
from typing_extensions import (  # noqa: E402, F401
    Annotated,
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

import pandas as pd  # noqa: E402, F401
from IPython.display import Markdown  # noqa: E402, F401

from langchain.agents import create_agent  # noqa: E402, F401
from langchain.tools import tool  # noqa: E402, F401
from langchain_core.messages import AIMessage, BaseMessage  # noqa: E402, F401
from langgraph.graph import END, START, StateGraph  # noqa: E402, F401
from langgraph.graph.message import add_messages  # noqa: E402, F401
from langgraph.prebuilt import InjectedState  # noqa: E402, F401
from langgraph.types import Checkpointer  # noqa: E402, F401

from ai_data_science_team.templates import BaseAgent  # noqa: E402, F401
from ai_data_science_team.utils.messages import get_tool_call_names  # noqa: E402, F401
from ai_data_science_team.utils.regex import format_agent_name  # noqa: E402, F401

AGENT_NAME = "model_monitoring_agent"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _psi(expected: "pd.Series", actual: "pd.Series", n_bins: int = 10) -> float:
    """Compute Population Stability Index between two continuous series."""
    import numpy as np  # noqa: E402, F401

    expected = expected.dropna()
    actual = actual.dropna()
    if expected.empty or actual.empty:
        return 0.0

    # Build bins from the reference (expected) distribution
    _, bin_edges = pd.cut(expected, bins=n_bins, retbins=True)
    bin_edges[0] = -np.inf
    bin_edges[-1] = np.inf

    exp_counts = pd.cut(expected, bins=bin_edges).value_counts(sort=False)
    act_counts = pd.cut(actual, bins=bin_edges).value_counts(sort=False)

    exp_pct = exp_counts / len(expected)
    act_pct = act_counts / len(actual)

    # Avoid log(0)
    eps = 1e-6
    exp_pct = exp_pct.clip(lower=eps)
    act_pct = act_pct.clip(lower=eps)

    import numpy as np  # noqa: E402, F401

    psi_value = float(np.sum((act_pct.values - exp_pct.values) * np.log(act_pct.values / exp_pct.values)))
    return round(abs(psi_value), 6)


def _psi_categorical(expected: "pd.Series", actual: "pd.Series") -> float:
    """Compute PSI for categorical columns."""
    import numpy as np  # noqa: E402, F401

    expected = expected.dropna().astype(str)
    actual = actual.dropna().astype(str)
    all_cats = set(expected.unique()) | set(actual.unique())
    eps = 1e-6

    psi = 0.0
    for cat in all_cats:
        exp_pct = max((expected == cat).mean(), eps)
        act_pct = max((actual == cat).mean(), eps)
        psi += (act_pct - exp_pct) * np.log(act_pct / exp_pct)
    return round(abs(psi), 6)


def _ks_test(reference: "pd.Series", current: "pd.Series") -> Tuple[float, float]:
    """KS two-sample test; returns (statistic, p_value)."""
    from scipy import stats  # type: ignore  # noqa: E402, F401

    ref = reference.dropna()
    cur = current.dropna()
    if ref.empty or cur.empty:
        return 0.0, 1.0
    stat, pval = stats.ks_2samp(ref.values, cur.values)
    return round(float(stat), 6), round(float(pval), 6)


def _drift_severity(psi: float) -> str:
    if psi < 0.1:
        return "stable"
    elif psi < 0.25:
        return "moderate"
    else:
        return "significant"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def detect_drift(
    reference_data_raw: Annotated[dict, InjectedState("reference_data_raw")],
    current_data_raw: Annotated[dict, InjectedState("current_data_raw")],
    drift_method: Annotated[str, InjectedState("drift_method")],
    psi_bins: Annotated[int, InjectedState("psi_bins")],
) -> Tuple[str, Dict]:
    """
    Tool: detect_drift
    Description:
        Detects feature distribution drift between a reference dataset and a
        current dataset using PSI and/or KS test.

    Parameters (injected from state):
        reference_data_raw : Reference (baseline) dataset as dict.
        current_data_raw   : Current (monitoring) dataset as dict.
        drift_method       : 'psi', 'ks', or 'both'.
        psi_bins           : Number of bins for PSI computation (default 10).

    Returns:
        Tuple[str, Dict]: text summary + artifact with per-feature drift metrics.
    """
    logger.info("    * Tool: detect_drift")

    import numpy as np  # noqa: E402, F401

    ref_df = pd.DataFrame(reference_data_raw)
    cur_df = pd.DataFrame(current_data_raw)

    common_cols = sorted(set(ref_df.columns) & set(cur_df.columns))
    if not common_cols:
        return "No common columns found between reference and current datasets.", {}

    method = (drift_method or "both").lower()
    n_bins = int(psi_bins) if psi_bins else 10

    feature_drift: List[Dict] = []
    drifted_features: List[str] = []

    for col in common_cols:
        ref_series = ref_df[col]
        cur_series = cur_df[col]
        is_numeric = pd.api.types.is_numeric_dtype(ref_series)

        result: Dict = {"feature": col, "is_numeric": is_numeric}

        if method in ("psi", "both"):
            if is_numeric:
                psi_val = _psi(ref_series, cur_series, n_bins=n_bins)
            else:
                psi_val = _psi_categorical(ref_series, cur_series)
            result["psi"] = psi_val
            result["psi_severity"] = _drift_severity(psi_val)

        if method in ("ks", "both") and is_numeric:
            ks_stat, ks_pval = _ks_test(ref_series, cur_series)
            result["ks_statistic"] = ks_stat
            result["ks_p_value"] = ks_pval
            result["ks_drifted"] = ks_pval < 0.05
        elif method in ("ks", "both") and not is_numeric:
            result["ks_statistic"] = None
            result["ks_p_value"] = None
            result["ks_drifted"] = None

        # Mark as drifted if PSI >= 0.1 or KS p < 0.05
        is_drifted = False
        if "psi" in result and result["psi"] >= 0.1:
            is_drifted = True
        if result.get("ks_drifted"):
            is_drifted = True
        result["drifted"] = is_drifted
        if is_drifted:
            drifted_features.append(col)

        feature_drift.append(result)

    # Sort by PSI descending (if available)
    if method in ("psi", "both"):
        feature_drift.sort(key=lambda x: x.get("psi", 0), reverse=True)

    n_drifted = len(drifted_features)
    overall_psi = (
        round(float(np.mean([f["psi"] for f in feature_drift if "psi" in f])), 6)
        if feature_drift
        else 0.0
    )

    artifact = {
        "method": method,
        "n_features_checked": len(common_cols),
        "n_drifted_features": n_drifted,
        "overall_mean_psi": overall_psi,
        "overall_severity": _drift_severity(overall_psi),
        "drifted_features": drifted_features,
        "feature_drift": feature_drift,
        "reference_n_rows": len(ref_df),
        "current_n_rows": len(cur_df),
    }

    severity = _drift_severity(overall_psi)
    content = (
        f"Drift detection complete ({method}).  "
        f"Checked {len(common_cols)} features — {n_drifted} show drift.  "
        f"Mean PSI: {overall_psi:.4f} ({severity}).  "
        f"Drifted: {', '.join(drifted_features[:5]) or 'none'}."
    )
    return content, artifact


@tool(response_format="content_and_artifact")
def compute_performance(
    y_true_raw: Annotated[dict, InjectedState("y_true_raw")],
    y_pred_raw: Annotated[dict, InjectedState("y_pred_raw")],
    task_type: Annotated[str, InjectedState("task_type")],
    baseline_metrics: Annotated[dict, InjectedState("baseline_metrics")],
) -> Tuple[str, Dict]:
    """
    Tool: compute_performance
    Description:
        Computes model performance metrics for classification or regression tasks.
        If baseline_metrics are provided, calculates degradation vs baseline.

    Parameters (injected from state):
        y_true_raw      : Dict with a single column of true labels.
        y_pred_raw      : Dict with a single column of predicted values.
        task_type       : 'classification' or 'regression'.
        baseline_metrics: Dict of {metric_name: baseline_value} for degradation comparison.
                          Pass empty dict if no baseline.

    Returns:
        Tuple[str, Dict]: text summary + artifact with metrics + degradation.
    """
    logger.info("    * Tool: compute_performance")

    import numpy as np  # noqa: E402, F401
    from sklearn import metrics as skm  # noqa

    y_true_df = pd.DataFrame(y_true_raw)
    y_pred_df = pd.DataFrame(y_pred_raw)

    if y_true_df.empty or y_pred_df.empty:
        return "No predictions/labels provided.", {}

    y_true = y_true_df.iloc[:, 0].values
    y_pred = y_pred_df.iloc[:, 0].values

    task = (task_type or "classification").lower()
    computed: Dict = {}

    if task == "classification":
        try:
            computed["accuracy"] = round(float(skm.accuracy_score(y_true, y_pred)), 6)
        except Exception:
            pass
        try:
            computed["weighted"] = round(
                float(skm.f1_score(y_true, y_pred, average="weighted", zero_division=0)), 6
            )
        except Exception:
            pass
        try:
            computed["precision_weighted"] = round(
                float(skm.precision_score(y_true, y_pred, average="weighted", zero_division=0)), 6
            )
        except Exception:
            pass
        try:
            computed["recall_weighted"] = round(
                float(skm.recall_score(y_true, y_pred, average="weighted", zero_division=0)), 6
            )
        except Exception:
            pass
        try:
            # ROC-AUC only for binary
            if len(np.unique(y_true)) == 2:
                computed["roc_auc"] = round(float(skm.roc_auc_score(y_true, y_pred)), 6)
        except Exception:
            pass
    else:  # regression
        try:
            computed["rmse"] = round(
                float(np.sqrt(skm.mean_squared_error(y_true, y_pred))), 6
            )
        except Exception:
            pass
        try:
            computed["mae"] = round(float(skm.mean_absolute_error(y_true, y_pred)), 6)
        except Exception:
            pass
        try:
            computed["r2"] = round(float(skm.r2_score(y_true, y_pred)), 6)
        except Exception:
            pass
        try:
            computed["mape"] = round(
                float(np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + 1e-9))) * 100), 4
            )
        except Exception:
            pass

    # Degradation vs baseline
    degradation: Dict = {}
    baseline = baseline_metrics or {}
    for metric, current_val in computed.items():
        if metric in baseline:
            base_val = float(baseline[metric])
            delta = round(current_val - base_val, 6)
            pct_change = round((delta / (abs(base_val) + 1e-9)) * 100, 4)
            # For regression losses (rmse, mae, mape) higher=worse; for others lower=worse
            loss_metrics = {"rmse", "mae", "mape"}
            degraded = (delta < 0) if metric not in loss_metrics else (delta > 0)
            degradation[metric] = {
                "baseline": base_val,
                "current": current_val,
                "delta": delta,
                "pct_change": pct_change,
                "degraded": degraded,
            }

    artifact = {
        "task_type": task,
        "n_samples": len(y_true),
        "metrics": computed,
        "degradation": degradation,
        "has_degradation": any(v["degraded"] for v in degradation.values()),
    }

    degraded_metrics = [k for k, v in degradation.items() if v["degraded"]]
    if degraded_metrics:
        deg_str = ", ".join(f"{m}: {degradation[m]['delta']:+.4f}" for m in degraded_metrics[:3])
        content = (
            f"Performance assessment complete ({task}).  "
            f"Current metrics: {', '.join(f'{k}={v:.4f}' for k, v in list(computed.items())[:3])}.  "
            f"DEGRADATION detected: {deg_str}."
        )
    else:
        content = (
            f"Performance assessment complete ({task}).  "
            f"Metrics: {', '.join(f'{k}={v:.4f}' for k, v in list(computed.items())[:3])}.  "
            "No degradation vs baseline."
        )
    return content, artifact


@tool(response_format="content")
def get_monitoring_params(
    drift_method: Annotated[str, InjectedState("drift_method")],
    psi_bins: Annotated[int, InjectedState("psi_bins")],
    task_type: Annotated[str, InjectedState("task_type")],
) -> str:
    """
    Tool: get_monitoring_params
    Description:
        Returns the current model monitoring agent configuration.

    Parameters (injected from state):
        drift_method : 'psi', 'ks', or 'both'.
        psi_bins     : Number of bins for PSI computation.
        task_type    : 'classification' or 'regression'.

    Returns:
        str: Human-readable configuration summary.
    """
    logger.info("    * Tool: get_monitoring_params")
    return (
        "Model monitoring agent configured with "
        f"drift_method='{drift_method}', psi_bins={psi_bins}, task_type='{task_type}'."
    )


MONITORING_TOOLS = [detect_drift, compute_performance, get_monitoring_params]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_model_monitoring_agent(
    model: Any,
    drift_method: str = "both",
    psi_bins: int = 10,
    task_type: str = "classification",
    baseline_metrics: Optional[Dict] = None,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Creates the compiled LangGraph StateGraph for the ModelMonitoringAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling).
    drift_method : str
        'psi', 'ks', or 'both' (default).
    psi_bins : int
        Bins used for PSI histogram computation.
    task_type : str
        'classification' (default) or 'regression'.
    baseline_metrics : dict, optional
        {metric_name: value} dict for degradation comparison.
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
        reference_data_raw: dict     # reference/baseline feature data
        current_data_raw: dict       # current/production feature data
        y_true_raw: dict             # ground-truth labels (single column)
        y_pred_raw: dict             # model predictions (single column)
        drift_method: str
        psi_bins: int
        task_type: str
        baseline_metrics: dict
        monitoring_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=MONITORING_TOOLS,
        state_schema=GraphState,  # type: ignore[arg-type]
        checkpointer=checkpointer,
        **create_react_agent_kwargs,
    )

    def prepare_messages(state: GraphState):
        logger.info(format_agent_name(AGENT_NAME))
        logger.info("    * PREPARE MESSAGES")
        if state.get("messages"):
            return {}
        return {"messages": [("user", state.get("user_instructions"))]}

    def run_react_agent(state: GraphState):
        logger.info("    * RUN REACT TOOL-CALLING AGENT FOR MODEL MONITORING")
        logger.info(f"    * drift_method={state.get('drift_method')}, task_type={state.get('task_type')}")

        system_hint = (
            "You are a Model Monitoring agent. "
            "Use 'detect_drift' to compare reference vs current feature distributions. "
            "Use 'compute_performance' if predictions and true labels are provided. "
            "Report the overall drift severity and any performance degradation."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload = {
            "messages": messages,
            "reference_data_raw": state.get("reference_data_raw") or {},
            "current_data_raw": state.get("current_data_raw") or {},
            "y_true_raw": state.get("y_true_raw") or {},
            "y_pred_raw": state.get("y_pred_raw") or {},
            "drift_method": state.get("drift_method", drift_method),
            "psi_bins": state.get("psi_bins", psi_bins),
            "task_type": state.get("task_type", task_type),
            "baseline_metrics": state.get("baseline_metrics") or baseline_metrics or {},
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING MODEL MONITORING RESULTS")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {"messages": [], "monitoring_results": {}, "tool_calls": []}

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
                content="Model monitoring completed. See monitoring_results for details.",
                name=AGENT_NAME,
            )

        monitoring_artifact: Dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            if art is not None and isinstance(art, dict):
                if "feature_drift" in art:
                    monitoring_artifact["drift"] = art
                elif "metrics" in art:
                    monitoring_artifact["performance"] = art
                else:
                    monitoring_artifact.update(art)

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                logger.info(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "monitoring_results": monitoring_artifact,
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


class ModelMonitoringAgent(BaseAgent):
    """
    A tool-calling agent that monitors ML model health in production.

    Detects feature/prediction distribution drift (PSI + KS test) and
    measures performance degradation against a baseline.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    drift_method : str
        Drift detection: 'psi', 'ks', or 'both' (default).
    psi_bins : int
        Histogram bins for PSI computation.  Default 10.
    task_type : str
        'classification' (default) or 'regression'.
    baseline_metrics : dict, optional
        {metric_name: value} baseline for degradation comparison.
    create_react_agent_kwargs / invoke_react_agent_kwargs : dict, optional
    checkpointer : Checkpointer, optional
    log_tool_calls : bool

    Examples
    --------
    >>> agent = ModelMonitoringAgent(model=llm, task_type='classification')
    >>> agent.invoke_agent(reference_data=ref_df, current_data=cur_df)
    >>> agent.get_drift_report()
    """

    def __init__(
        self,
        model: Any,
        drift_method: str = "both",
        psi_bins: int = 10,
        task_type: str = "classification",
        baseline_metrics: Optional[Dict] = None,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "drift_method": drift_method,
            "psi_bins": psi_bins,
            "task_type": task_type,
            "baseline_metrics": baseline_metrics or {},
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_model_monitoring_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        reference_data: pd.DataFrame = None,
        current_data: pd.DataFrame = None,
        y_true: pd.Series = None,
        y_pred: pd.Series = None,
        user_instructions: str = None,
        drift_method: str = None,
        task_type: str = None,
        baseline_metrics: Optional[Dict] = None,
        **kwargs,
    ):
        """
        Run the model monitoring agent.

        Parameters
        ----------
        reference_data : pd.DataFrame
            Baseline/reference feature dataset.
        current_data : pd.DataFrame
            Current/production feature dataset.
        y_true : pd.Series, optional
            Ground-truth labels for performance computation.
        y_pred : pd.Series, optional
            Model predictions for performance computation.
        user_instructions : str, optional
            Natural-language task.
        drift_method : str, optional
            Override for this call only.
        task_type : str, optional
            Override for this call only.
        baseline_metrics : dict, optional
            Override baseline metrics for this call only.
        """
        if user_instructions is None:
            m = drift_method or self._params["drift_method"]
            user_instructions = (
                f"Monitor the model health: detect feature drift ({m}) between "
                "the reference and current datasets. "
                "Report any features with significant drift and overall drift severity."
            )
            if y_true is not None and y_pred is not None:
                user_instructions += (
                    " Also compute current model performance metrics and compare "
                    "to baseline if available."
                )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        def _to_dict(obj):
            if obj is None:
                return {}
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict()
            if isinstance(obj, pd.Series):
                return obj.to_frame().to_dict()
            return {}

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "reference_data_raw": _to_dict(reference_data),
                "current_data_raw": _to_dict(current_data),
                "y_true_raw": _to_dict(y_true),
                "y_pred_raw": _to_dict(y_pred),
                "drift_method": drift_method or self._params["drift_method"],
                "psi_bins": self._params["psi_bins"],
                "task_type": task_type or self._params["task_type"],
                "baseline_metrics": baseline_metrics if baseline_metrics is not None else self._params["baseline_metrics"],
            },
            **kwargs,
        )
        self.response = response
        return None

    def get_monitoring_results(self) -> Optional[Dict]:
        """Returns the full monitoring results dict (keys: 'drift', 'performance')."""
        if not self.response:
            return None
        return self.response.get("monitoring_results")

    def get_drift_report(self) -> Optional[Dict]:
        """Returns the drift detection report dict."""
        r = self.get_monitoring_results()
        return r.get("drift") if r else None

    def get_drifted_features(self) -> Optional[List[str]]:
        """Returns the list of feature names with detected drift."""
        drift = self.get_drift_report()
        return drift.get("drifted_features") if drift else None

    def get_drift_severity(self) -> Optional[str]:
        """Returns the overall drift severity: 'stable', 'moderate', or 'significant'."""
        drift = self.get_drift_report()
        return drift.get("overall_severity") if drift else None

    def get_mean_psi(self) -> Optional[float]:
        """Returns the mean PSI across all features."""
        drift = self.get_drift_report()
        return drift.get("overall_mean_psi") if drift else None

    def get_performance_metrics(self) -> Optional[Dict]:
        """Returns computed performance metrics dict."""
        r = self.get_monitoring_results()
        if r is None:
            return None
        return r.get("performance", {}).get("metrics")

    def get_degradation_report(self) -> Optional[Dict]:
        """Returns per-metric degradation comparison vs baseline."""
        r = self.get_monitoring_results()
        if r is None:
            return None
        return r.get("performance", {}).get("degradation")

    def has_degradation(self) -> Optional[bool]:
        """Returns True if any metric shows degradation vs baseline."""
        r = self.get_monitoring_results()
        if r is None:
            return None
        return r.get("performance", {}).get("has_degradation")

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
