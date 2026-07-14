"""
AnomalyDetectionAgent
=====================
A tool-calling agent that detects anomalies/outliers in tabular data using
scikit-learn (and optionally PyOD) algorithms. Follows the EDAToolsAgent
react-agent pattern using tools from the ToolRegistry.

Supported methods
-----------------
* IsolationForest  - sklearn IsolationForest
* LOF              - sklearn LocalOutlierFactor
* HBOS             - PyOD HBOS (falls back to IsolationForest when PyOD absent)
* COPOD            - PyOD COPOD (falls back to IsolationForest when PyOD absent)
* AutoEnsemble     - majority-vote of IsolationForest + LOF (default)
"""

from __future__ import annotations


import logging

logger = logging.getLogger(__name__)
from typing_extensions import (
    Annotated,
    Any,
    Dict,
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

AGENT_NAME = "anomaly_detection_agent"


@tool(response_format="content_and_artifact")
def detect_anomalies(
    data_raw: Annotated[dict, InjectedState("data_raw")],
    method: Annotated[str, InjectedState("method")],
    contamination: Annotated[float, InjectedState("contamination")],
) -> Tuple[str, Dict]:
    """
    Tool: detect_anomalies
    Description:
        Detects anomalies/outliers in the dataset using the specified algorithm.
        Returns a structured artifact with anomaly indices, scores, and summary stats.

    Parameters:
        data_raw     : Raw dataset (injected from state).
        method       : Algorithm name – one of IsolationForest, LOF, HBOS, COPOD,
                       AutoEnsemble (injected from state).
        contamination: Expected proportion of outliers [0, 0.5] (injected from state).

    Returns:
        Tuple[str, Dict]: text summary + artifact dict with anomaly details.
    """
    logger.info("    * Tool: detect_anomalies")

    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.preprocessing import StandardScaler

    df = pd.DataFrame(data_raw)
    numeric_df = df.select_dtypes(include=[np.number]).copy()
    numeric_df = numeric_df.fillna(numeric_df.median(numeric_only=True))

    if numeric_df.empty:
        return "No numeric columns found – cannot detect anomalies.", {}

    X = StandardScaler().fit_transform(numeric_df)

    def _run_isolation_forest():
        clf = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        clf.fit(X)
        lbl = clf.predict(X)
        scr = -clf.decision_function(X)
        return lbl, scr

    def _run_lof():
        clf = LocalOutlierFactor(contamination=contamination, novelty=False)
        lbl = clf.fit_predict(X)
        scr = -clf.negative_outlier_factor_
        return lbl, scr

    def _run_pyod(model_name: str):
        try:
            if model_name == "HBOS":
                from pyod.models.hbos import HBOS
                clf = HBOS(contamination=contamination)
            elif model_name == "COPOD":
                from pyod.models.copod import COPOD
                clf = COPOD(contamination=contamination)
            else:
                raise ImportError("Unknown PyOD model")
            clf.fit(X)
            lbl = (clf.labels_ * -2 + 1).astype(int)
            scr = clf.decision_scores_.tolist()
            return lbl, scr
        except Exception:
            return _run_isolation_forest()

    m = method.strip() if method else "AutoEnsemble"

    if m == "IsolationForest":
        labels, scores = _run_isolation_forest()
    elif m == "LOF":
        labels, scores = _run_lof()
    elif m == "HBOS":
        labels, scores = _run_pyod("HBOS")
    elif m == "COPOD":
        labels, scores = _run_pyod("COPOD")
    else:
        labels_if, scores_if = _run_isolation_forest()
        labels_lof, scores_lof = _run_lof()
        combined = labels_if + labels_lof
        labels = np.where(combined <= -1, -1, 1)
        scores_if_norm = (scores_if - scores_if.min()) / (scores_if.max() - scores_if.min() + 1e-9)
        scores_lof_arr = np.array(scores_lof)
        scores_lof_norm = (scores_lof_arr - scores_lof_arr.min()) / (
            scores_lof_arr.max() - scores_lof_arr.min() + 1e-9
        )
        scores = ((scores_if_norm + scores_lof_norm) / 2).tolist()

    labels = list(labels)
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    else:
        scores = list(scores)

    anomaly_indices = [int(i) for i, lbl in enumerate(labels) if lbl == -1]
    n_anomalies = len(anomaly_indices)
    total = len(labels)
    anomaly_rate = round(n_anomalies / total, 4) if total > 0 else 0.0

    top_idx = sorted(anomaly_indices, key=lambda i: scores[i], reverse=True)[:20]
    top_df = df.iloc[top_idx].copy()
    top_df["__anomaly_score__"] = [round(scores[i], 4) for i in top_idx]
    top_anomalies = top_df.to_dict(orient="records")

    artifact = {
        "method": m,
        "n_anomalies": n_anomalies,
        "anomaly_rate": anomaly_rate,
        "total_samples": total,
        "anomaly_indices": anomaly_indices,
        "anomaly_scores": [round(s, 4) for s in scores],
        "top_anomalies": top_anomalies,
    }

    content = (
        f"Anomaly detection complete using {m}. "
        f"Found {n_anomalies} anomalies out of {total} samples "
        f"({anomaly_rate * 100:.2f}% contamination)."
    )
    return content, artifact


@tool(response_format="content")
def get_anomaly_params(
    method: Annotated[str, InjectedState("method")],
    contamination: Annotated[float, InjectedState("contamination")],
) -> str:
    """
    Tool: get_anomaly_params
    Description:
        Returns the current anomaly detection configuration (method and contamination).

    Parameters:
        method       : Algorithm name (injected from state).
        contamination: Expected fraction of outliers (injected from state).

    Returns:
        str: Human-readable summary of the current parameters.
    """
    logger.info("    * Tool: get_anomaly_params")
    return f"Anomaly detection will use method='{method}' with contamination={contamination}."


ANOMALY_TOOLS = [detect_anomalies, get_anomaly_params]


def make_anomaly_detection_agent(
    model: Any,
    method: str = "AutoEnsemble",
    contamination: float = 0.05,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Creates the compiled LangGraph StateGraph for the AnomalyDetectionAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM used for tool-calling.
    method : str
        Default detection algorithm. The user can override at invoke time.
    contamination : float
        Expected fraction of outliers (0 < contamination < 0.5).
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer.
    log_tool_calls : bool
        Whether to print tool call names during execution.

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
        method: str
        contamination: float
        anomaly_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=ANOMALY_TOOLS,
        state_schema=GraphState,
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
        logger.info("    * RUN REACT TOOL-CALLING AGENT FOR ANOMALY DETECTION")
        m = state.get("method", method)
        c = state.get("contamination", contamination)
        logger.info(f"    * method={m}, contamination={c}")

        system_hint = (
            "You are an Anomaly Detection agent. "
            "Call 'detect_anomalies' to identify outliers in the dataset, "
            "then return a concise summary of the findings including the number "
            "of anomalies detected and the anomaly rate."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))
        ]
        messages = [("system", system_hint)] + list(base_messages)

        input_payload = {
            "messages": messages,
            "data_raw": state.get("data_raw"),
            "method": m,
            "contamination": c,
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)

    def post_process(state: GraphState):
        logger.info("    * POST-PROCESSING ANOMALY DETECTION RESULTS")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {"messages": [], "anomaly_results": {}, "tool_calls": []}

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
                content="Anomaly detection completed. See anomaly_results for details.",
                name=AGENT_NAME,
            )

        anomaly_artifact: Dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            if art is not None and isinstance(art, dict):
                anomaly_artifact.update(art)

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                logger.info(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "anomaly_results": anomaly_artifact,
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

    app = workflow.compile(checkpointer=checkpointer, name=AGENT_NAME)
    return app


class AnomalyDetectionAgent(BaseAgent):
    """
    A tool-calling agent that detects anomalies/outliers in tabular data.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    method : str
        Detection algorithm: 'IsolationForest', 'LOF', 'HBOS', 'COPOD', or
        'AutoEnsemble' (default).
    contamination : float
        Expected fraction of outliers (0 < contamination <= 0.5). Default 0.05.
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer (enables memory across sessions).
    log_tool_calls : bool
        Print tool call names when True.

    Examples
    --------
    >>> agent = AnomalyDetectionAgent(model=llm, method="IsolationForest")
    >>> agent.invoke_agent(data_raw=df)
    >>> agent.get_anomaly_indices()
    """

    def __init__(
        self,
        model: Any,
        method: str = "AutoEnsemble",
        contamination: float = 0.05,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "method": method,
            "contamination": contamination,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_anomaly_detection_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        data_raw: pd.DataFrame = None,
        user_instructions: str = None,
        method: str = None,
        contamination: float = None,
        **kwargs,
    ):
        """
        Run the anomaly detection agent.

        Parameters
        ----------
        data_raw : pd.DataFrame
            Input data to scan for anomalies.
        user_instructions : str, optional
            Natural-language task description. Defaults to a generic prompt.
        method : str, optional
            Override the default method for this call only.
        contamination : float, optional
            Override the default contamination for this call only.
        """
        if user_instructions is None:
            m = method or self._params["method"]
            c = contamination if contamination is not None else self._params["contamination"]
            user_instructions = (
                f"Detect anomalies in the dataset using the {m} algorithm "
                f"with contamination={c}. Report the number of anomalies found."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "data_raw": data_raw.to_dict() if data_raw is not None else None,
                "method": method or self._params["method"],
                "contamination": contamination if contamination is not None else self._params["contamination"],
            },
            **kwargs,
        )
        self.response = response
        return None

    def get_anomaly_result(self) -> Optional[Dict]:
        """Returns the full anomaly result artifact dictionary."""
        if not self.response:
            return None
        return self.response.get("anomaly_results")

    def get_anomaly_indices(self) -> Optional[list]:
        """Returns the list of integer row indices identified as anomalies."""
        r = self.get_anomaly_result()
        return r.get("anomaly_indices") if r else None

    def get_n_anomalies(self) -> Optional[int]:
        """Returns the number of anomalies detected."""
        r = self.get_anomaly_result()
        return r.get("n_anomalies") if r else None

    def get_anomaly_rate(self) -> Optional[float]:
        """Returns the anomaly rate (fraction of samples, 0–1)."""
        r = self.get_anomaly_result()
        return r.get("anomaly_rate") if r else None

    def get_top_anomalies(self, as_dataframe: bool = True):
        """
        Returns the top anomalous rows (up to 20, sorted by anomaly score).

        Parameters
        ----------
        as_dataframe : bool
            If True return a DataFrame; otherwise return a list of dicts.
        """
        r = self.get_anomaly_result()
        if r is None:
            return None
        top = r.get("top_anomalies", [])
        if as_dataframe:
            return pd.DataFrame(top)
        return top

    def get_anomaly_scores(self) -> Optional[list]:
        """Returns anomaly scores for every sample (higher = more anomalous)."""
        r = self.get_anomaly_result()
        return r.get("anomaly_scores") if r else None

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

    def get_tool_calls(self) -> Optional[list]:
        """Returns the list of tool names that were called."""
        if not self.response:
            return None
        return self.response.get("tool_calls")
