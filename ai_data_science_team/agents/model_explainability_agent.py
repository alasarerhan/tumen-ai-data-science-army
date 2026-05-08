"""
ModelExplainabilityAgent
========================
A tool-calling agent that explains ML models using SHAP and LIME.
Follows the EDAToolsAgent react-agent pattern.

Tools
-----
* explain_with_shap  – global feature-importance via SHAP
* explain_with_lime  – local (single-instance) explanation via LIME
* get_explainability_params – returns current configuration

The agent stores the trained sklearn model via ``InjectedState`` rather than
serialization so it works cleanly inside a LangGraph workflow without
checkpointing.  (Checkpointing a non-serialisable model is not supported.)
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

AGENT_NAME = "model_explainability_agent"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def explain_with_shap(
    model_artifact: Annotated[Any, InjectedState("model_artifact")],
    data_raw: Annotated[dict, InjectedState("data_raw")],
    background_data_raw: Annotated[dict, InjectedState("background_data_raw")],
    n_samples: Annotated[int, InjectedState("n_samples")],
) -> Tuple[str, Dict]:
    """
    Tool: explain_with_shap
    Description:
        Computes SHAP feature importances for the provided model and data.
        Returns mean absolute SHAP values per feature plus per-sample values for
        the first n_samples rows.

    Parameters (all injected from state):
        model_artifact    : Trained scikit-learn compatible model.
        data_raw          : Feature data to explain (as dict).
        background_data_raw : Background/reference data for the SHAP explainer.
        n_samples         : Number of data rows to compute SHAP values for.

    Returns:
        Tuple[str, Dict]: text summary + artifact with SHAP importance dict.
    """
    print("    * Tool: explain_with_shap")

    import numpy as np

    try:
        import shap  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "SHAP is required for this tool.  Install with: pip install shap"
        ) from exc

    explain_df = pd.DataFrame(data_raw)
    background_df = pd.DataFrame(background_data_raw)
    feature_names: List[str] = list(explain_df.columns)

    # Limit samples to avoid OOM
    n = min(n_samples, len(explain_df))
    explain_df = explain_df.iloc[:n]

    # Choose explainer strategy
    try:
        # Try TreeExplainer first (fastest for tree-based models)
        explainer = shap.TreeExplainer(
            model_artifact, data=background_df, check_additivity=False
        )
        shap_values = explainer.shap_values(explain_df)
    except Exception:
        try:
            # Fall back to KernelExplainer (works for any model)
            n_bg = min(50, len(background_df))
            summary_bg = shap.kmeans(background_df, n_bg)
            predict_fn = (
                model_artifact.predict_proba
                if hasattr(model_artifact, "predict_proba")
                else model_artifact.predict
            )
            explainer = shap.KernelExplainer(predict_fn, summary_bg)
            shap_values = explainer.shap_values(explain_df.values[:n], nsamples=100)
        except Exception as exc2:
            return f"SHAP explanation failed: {exc2}", {}

    # Robust handling of different SHAP output formats across library versions.
    # KernelExplainer (binary): list of 2 arrays, each (n_samples, n_features)
    # TreeExplainer old: list of 2 arrays
    # TreeExplainer new (≥0.41): ndarray of shape (n_samples, n_features, n_classes)
    # Regression / single-output: ndarray (n_samples, n_features)
    if isinstance(shap_values, list):
        # Pick the positive / last class array
        sv = np.array(shap_values[-1])
    else:
        sv = np.array(shap_values)

    # Ensure exactly 2D: (n_samples, n_features)
    if sv.ndim == 1:
        sv = sv.reshape(1, -1)
    elif sv.ndim == 3:
        # (n_samples, n_features, n_classes) → use last class column
        sv = sv[:, :, -1]
    elif sv.ndim > 3:
        # Flatten extra dimensions as a last resort
        sv = sv.reshape(sv.shape[0], sv.shape[1], -1)[:, :, -1]

    # mean_abs is now guaranteed 1D
    mean_abs_arr = np.abs(sv).mean(axis=0)
    if mean_abs_arr.ndim > 1:
        mean_abs_arr = mean_abs_arr.mean(axis=-1)
    mean_abs = mean_abs_arr.tolist()
    importance = {feat: round(float(val), 6) for feat, val in zip(feature_names, mean_abs)}
    top_features = sorted(importance.items(), key=lambda kv: kv[1], reverse=True)

    # Per-row shap values (for downstream use)
    per_row = [
        {feat: round(float(v), 6) for feat, v in zip(feature_names, row)}
        for row in sv.tolist()
    ]

    artifact = {
        "feature_importance": importance,
        "top_features": top_features[:20],
        "shap_values_per_row": per_row[:10],  # keep artifact small
        "n_samples_explained": n,
    }

    top_str = ", ".join(f"{f}={v:.4f}" for f, v in top_features[:5])
    content = (
        f"SHAP explanation complete for {n} samples.  "
        f"Top features by mean |SHAP|: {top_str}."
    )
    return content, artifact


@tool(response_format="content_and_artifact")
def explain_with_lime(
    model_artifact: Annotated[Any, InjectedState("model_artifact")],
    data_raw: Annotated[dict, InjectedState("data_raw")],
    background_data_raw: Annotated[dict, InjectedState("background_data_raw")],
    sample_index: int = 0,
) -> Tuple[str, Dict]:
    """
    Tool: explain_with_lime
    Description:
        Produces a local LIME explanation for the sample at `sample_index` in data_raw.

    Parameters (model_artifact, data_raw, background_data_raw injected from state):
        model_artifact      : Trained scikit-learn compatible model.
        data_raw            : Feature data (as dict).
        background_data_raw : Training data used to fit the LIME explainer.
        sample_index        : Row index (0-based) to explain (provided by LLM).

    Returns:
        Tuple[str, Dict]: text summary + artifact dict.
    """
    print(f"    * Tool: explain_with_lime (sample_index={sample_index})")

    try:
        import lime  # type: ignore
        import lime.lime_tabular  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "LIME is required for this tool.  Install with: pip install lime"
        ) from exc

    import numpy as np

    explain_df = pd.DataFrame(data_raw)
    background_df = pd.DataFrame(background_data_raw)
    feature_names: List[str] = list(explain_df.columns)

    # Determine task type
    is_classifier = hasattr(model_artifact, "predict_proba")
    mode = "classification" if is_classifier else "regression"

    try:
        n_classes = (
            len(model_artifact.classes_)
            if hasattr(model_artifact, "classes_")
            else 2
        )
        class_names: Optional[List[str]] = (
            [str(c) for c in model_artifact.classes_]
            if hasattr(model_artifact, "classes_")
            else None
        )
    except Exception:
        n_classes = 2
        class_names = None

    explainer = lime.lime_tabular.LimeTabularExplainer(
        training_data=background_df.values.astype(float),
        feature_names=feature_names,
        class_names=class_names,
        mode=mode,
        random_state=42,
        verbose=False,
    )

    idx = min(sample_index, len(explain_df) - 1)
    instance = explain_df.iloc[idx].values.astype(float)

    predict_fn = (
        model_artifact.predict_proba if is_classifier else model_artifact.predict
    )

    exp = explainer.explain_instance(
        instance, predict_fn, num_features=min(15, len(feature_names))
    )
    lime_list = exp.as_list()

    artifact = {
        "sample_index": idx,
        "mode": mode,
        "lime_explanation": lime_list,
        "top_positive": [(f, round(v, 6)) for f, v in lime_list if v > 0][:10],
        "top_negative": [(f, round(v, 6)) for f, v in lime_list if v < 0][:10],
    }

    top_pos = ", ".join(f"{f}={v:.4f}" for f, v in artifact["top_positive"][:3])
    top_neg = ", ".join(f"{f}={v:.4f}" for f, v in artifact["top_negative"][:3])
    content = (
        f"LIME explanation for sample index {idx} ({mode}).  "
        f"Top positive factors: {top_pos or 'none'}.  "
        f"Top negative factors: {top_neg or 'none'}."
    )
    return content, artifact


@tool(response_format="content")
def get_explainability_params(
    n_samples: Annotated[int, InjectedState("n_samples")],
) -> str:
    """
    Tool: get_explainability_params
    Description:
        Returns the current explainability configuration.

    Parameters:
        n_samples : Max samples to compute SHAP values for (injected from state).

    Returns:
        str: Current configuration summary.
    """
    print("    * Tool: get_explainability_params")
    return f"Model explainability agent is configured with n_samples={n_samples}."


EXPLAINABILITY_TOOLS = [explain_with_shap, explain_with_lime, get_explainability_params]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_model_explainability_agent(
    model: Any,
    n_samples: int = 100,
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Creates the compiled LangGraph StateGraph for the ModelExplainabilityAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM used for tool-calling (e.g. ChatOpenAI).
    n_samples : int
        Maximum number of rows to compute SHAP values for.
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer (not recommended when model_artifact is not
        JSON-serialisable).
    log_tool_calls : bool
        Print tool call names when True.

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
        model_artifact: Any          # sklearn model object
        data_raw: dict               # feature data to explain
        background_data_raw: dict    # background/training data for SHAP/LIME
        n_samples: int
        explainability_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=EXPLAINABILITY_TOOLS,
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
        print("    * RUN REACT TOOL-CALLING AGENT FOR MODEL EXPLAINABILITY")

        system_hint = (
            "You are a Model Explainability agent. "
            "Use 'explain_with_shap' to compute global SHAP feature importances for the model. "
            "Optionally use 'explain_with_lime' for a local explanation of a specific instance. "
            "Return a concise summary of the most important features."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload = {
            "messages": messages,
            "model_artifact": state.get("model_artifact"),
            "data_raw": state.get("data_raw"),
            "background_data_raw": state.get("background_data_raw"),
            "n_samples": state.get("n_samples", n_samples),
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        print("    * POST-PROCESSING MODEL EXPLAINABILITY RESULTS")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {"messages": [], "explainability_results": {}, "tool_calls": []}

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
                content="Model explanation completed. See explainability_results for details.",
                name=AGENT_NAME,
            )

        # Collect artifacts from tool messages (merge all artifact dicts)
        explain_artifact: Dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            name = getattr(msg, "name", "") or ""
            if art is not None and isinstance(art, dict):
                if "feature_importance" in art:
                    explain_artifact["shap"] = art
                elif "lime_explanation" in art:
                    explain_artifact["lime"] = art
                else:
                    explain_artifact.update(art)

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                print(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "explainability_results": explain_artifact,
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


class ModelExplainabilityAgent(BaseAgent):
    """
    A tool-calling agent that explains ML model predictions using SHAP and LIME.

    Parameters
    ----------
    model : Any
        LangChain LLM used for tool-calling (e.g. ChatOpenAI).
    n_samples : int
        Maximum rows to use for SHAP computation.  Default 100.
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer (not recommended when model_artifact is not
        JSON-serialisable).
    log_tool_calls : bool
        Print tool call names when True.

    Examples
    --------
    >>> agent = ModelExplainabilityAgent(model=llm)
    >>> agent.invoke_agent(
    ...     model_artifact=trained_clf,
    ...     background_data=X_train,
    ...     explain_data=X_test,
    ... )
    >>> agent.get_shap_importance()
    """

    def __init__(
        self,
        model: Any,
        n_samples: int = 100,
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "n_samples": n_samples,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_model_explainability_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        model_artifact: Any = None,
        background_data: pd.DataFrame = None,
        explain_data: pd.DataFrame = None,
        user_instructions: str = None,
        n_samples: int = None,
        **kwargs,
    ):
        """
        Run the model explainability agent.

        Parameters
        ----------
        model_artifact : sklearn estimator
            Trained ML model (must implement ``predict`` or ``predict_proba``).
        background_data : pd.DataFrame
            Reference dataset for SHAP KernelExplainer background / LIME training.
        explain_data : pd.DataFrame
            Feature data for which explanations are requested.
        user_instructions : str, optional
            Natural-language instructions.  Defaults to a generic prompt.
        n_samples : int, optional
            Override the default n_samples for this call only.
        """
        if user_instructions is None:
            user_instructions = (
                "Explain the model predictions using SHAP to identify the most "
                "important features globally."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        eff_n = n_samples if n_samples is not None else self._params["n_samples"]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "model_artifact": model_artifact,
                "data_raw": explain_data.to_dict() if explain_data is not None else {},
                "background_data_raw": (
                    background_data.to_dict() if background_data is not None else {}
                ),
                "n_samples": eff_n,
            },
            **kwargs,
        )
        self.response = response
        return None

    def get_explanation(self) -> Optional[Dict]:
        """Returns the full explainability results dictionary."""
        if not self.response:
            return None
        return self.response.get("explainability_results")

    def get_shap_importance(self) -> Optional[Dict]:
        """
        Returns the SHAP feature importance dict ``{feature_name: mean_abs_shap}``.
        """
        results = self.get_explanation()
        if results is None:
            return None
        shap_block = results.get("shap", {})
        return shap_block.get("feature_importance")

    def get_top_features(self, n: int = 10) -> Optional[List]:
        """
        Returns the top-n features sorted by SHAP importance (descending).

        Returns a list of (feature_name, mean_abs_shap) tuples.
        """
        results = self.get_explanation()
        if results is None:
            return None
        shap_block = results.get("shap", {})
        top = shap_block.get("top_features", [])
        return top[:n]

    def get_top_feature(self) -> Optional[str]:
        """Returns the single most important feature name."""
        top = self.get_top_features(n=1)
        if top:
            return top[0][0]
        return None

    def get_lime_explanation(self) -> Optional[List]:
        """
        Returns the LIME explanation as a list of (feature_condition, weight) tuples.
        """
        results = self.get_explanation()
        if results is None:
            return None
        lime_block = results.get("lime", {})
        return lime_block.get("lime_explanation")

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
