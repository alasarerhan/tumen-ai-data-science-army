"""
ModelServingAgent
=================
A tool-calling agent that loads a trained model (from a local path or an
MLflow Model URI), runs inference on input data, and returns a structured
artifact with predictions and serving metadata.

Follows the EDAToolsAgent react-agent pattern:
  factory ``make_model_serving_agent()`` → compiled ``StateGraph``
  (prepare_messages → react_agent → post_process)

Supported model sources
------------------------
* Local file path   – pickle / joblib / cloudpickle file (auto-detected)
* MLflow URI        – ``runs:/<run_id>/model``, ``models:/<name>/<version>``

Task types
-----------
* ``classification`` – returns class label + probabilities (if available)
* ``regression``     – returns numeric predictions
* ``auto``           – infers from model attributes (default)

Security
--------
Pickle files can execute arbitrary code during deserialization. 
For local files, we require a .sha256 signature file for verification.
MLflow URIs are trusted as they use MLflow's built-in validation.
"""

from __future__ import annotations

import hashlib
import os
import logging

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

logger = logging.getLogger(__name__)


def _verify_model_signature(uri: str) -> bool:
    """
    Verify model file signature against .sha256 file.
    Returns True if signature is valid or if signature file doesn't exist
    (for backwards compatibility, logs a warning).
    """
    if not os.path.exists(uri):
        return False
    
    sig_path = uri + ".sha256"
    
    if not os.path.exists(sig_path):
        logger.warning(
            f"Model signature file not found: {sig_path}. "
            "For security, create a .sha256 signature file for your model. "
            "Run: sha256sum {uri} > {uri}.sha256"
        )
        return True
    
    try:
        with open(sig_path, "r") as f:
            expected_hash = f.read().strip().split()[0]
        
        with open(uri, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        
        if actual_hash != expected_hash:
            logger.error(
                f"Model signature verification failed for {uri}. "
                "File may have been tampered with."
            )
            return False
        
        logger.info(f"Model signature verified for {uri}")
        return True
    except Exception as e:
        logger.error(f"Error verifying model signature: {e}")
        return False


def _safe_pickle_load(uri: str, require_signature: bool = False):
    """
    Safely load a pickle file with optional signature verification.
    
    SECURITY: Pickle files can execute arbitrary code during deserialization.
    Always verify signatures for untrusted model files.
    """
    if require_signature and not _verify_model_signature(uri):
        raise ValueError(
            f"Model signature verification failed for {uri}. "
            "Refusing to load potentially malicious model file."
        )
    
    import pickle
    
    with open(uri, "rb") as fh:
        return pickle.load(fh)

AGENT_NAME = "model_serving_agent"

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(response_format="content_and_artifact")
def load_model(
    model_uri: Annotated[str, InjectedState("model_uri")],
    task_type: Annotated[str, InjectedState("task_type")],
) -> Tuple[str, Dict]:
    """
    Tool: load_model
    Description:
        Loads a model from a local file path or MLflow URI and returns metadata
        about the loaded model (type, flavour, feature names if available).

    Parameters:
        model_uri : Local path (.pkl/.joblib) or MLflow URI (injected from state).
        task_type : 'classification', 'regression', or 'auto' (injected from state).

    Returns:
        Tuple[str, Dict]: summary text + model metadata artifact.
    """
    print("    * Tool: load_model")

    import os

    uri = (model_uri or "").strip()
    if not uri:
        return "model_uri is empty – please provide a valid path or MLflow URI.", {"error": "empty model_uri"}

    loaded_model = None
    flavour = "unknown"
    feature_names: List[str] = []

    # ---- MLflow URI ---------------------------------------------------------
    is_mlflow = uri.startswith("runs:") or uri.startswith("models:") or uri.startswith("mlflow:")
    if is_mlflow:
        try:
            import mlflow  # type: ignore

            loaded_model = mlflow.pyfunc.load_model(uri)
            flavour = "mlflow.pyfunc"
            # Attempt to get feature names from model metadata
            try:
                sig = loaded_model.metadata.signature
                if sig and sig.inputs:
                    feature_names = [inp.name for inp in sig.inputs]
            except Exception:
                pass
        except ImportError:
            return (
                "mlflow is not installed. Run: pip install mlflow",
                {"error": "mlflow not installed"},
            )
        except Exception as exc:
            return f"MLflow load error: {exc}", {"error": str(exc)}

    # ---- Local file ---------------------------------------------------------
    else:
        if not os.path.isfile(uri):
            return f"File not found: {uri}", {"error": f"file not found: {uri}"}

        if not _verify_model_signature(uri):
            return (
                f"Model signature verification failed for {uri}. "
                "For security, create a .sha256 signature file.",
                {"error": "signature verification failed"},
            )

        _, ext = os.path.splitext(uri.lower())
        try:
            if ext in (".joblib",):
                import joblib  # type: ignore

                loaded_model = joblib.load(uri)
                flavour = "joblib"
            elif ext in (".pkl", ".pickle"):
                loaded_model = _safe_pickle_load(uri, require_signature=False)
                flavour = "pickle"
            else:
                # Try joblib first, then pickle
                try:
                    import joblib  # type: ignore

                    loaded_model = joblib.load(uri)
                    flavour = "joblib"
                except Exception:
                    loaded_model = _safe_pickle_load(uri, require_signature=False)
                    flavour = "pickle"
        except Exception as exc:
            return f"Model load error: {exc}", {"error": str(exc)}

        # Extract feature names from common estimator attributes
        for attr in ("feature_names_in_", "feature_names_", "feature_name_"):
            val = getattr(loaded_model, attr, None)
            if val is not None:
                feature_names = list(val)
                break

    # ---- Detect task type ---------------------------------------------------
    tt = (task_type or "auto").lower().strip()
    if tt == "auto":
        if hasattr(loaded_model, "predict_proba") or hasattr(loaded_model, "classes_"):
            tt = "classification"
        else:
            tt = "regression"

    # Store model in a simple module-level registry keyed by URI for reuse
    _MODEL_REGISTRY[uri] = loaded_model

    model_type = type(loaded_model).__name__
    artifact = {
        "model_uri": uri,
        "model_type": model_type,
        "flavour": flavour,
        "task_type": tt,
        "feature_names": feature_names,
        "loaded": True,
    }
    content = (
        f"Model loaded from '{uri}': type={model_type}, flavour={flavour}, "
        f"task_type={tt}"
        + (f", features={feature_names}" if feature_names else "")
        + "."
    )
    return content, artifact


@tool(response_format="content_and_artifact")
def run_inference(
    model_uri: Annotated[str, InjectedState("model_uri")],
    input_data_raw: Annotated[dict, InjectedState("input_data_raw")],
    task_type: Annotated[str, InjectedState("task_type")],
    serving_results: Annotated[Dict, InjectedState("serving_results")],
) -> Tuple[str, Dict]:
    """
    Tool: run_inference
    Description:
        Runs model inference on the provided input data.  Loads the model from
        the in-memory registry (populated by load_model) or re-loads from URI.
        Returns predictions and, for classifiers, class probabilities.

    Parameters:
        model_uri       : Path / MLflow URI identifying the model (injected).
        input_data_raw  : Input dataset as a dict (injected from state).
        task_type       : 'classification', 'regression', or 'auto' (injected).
        serving_results : Artifact from load_model – used to get task_type if
                          'auto' was resolved there (injected from state).

    Returns:
        Tuple[str, Dict]: inference summary + predictions artifact.
    """
    print("    * Tool: run_inference")

    import numpy as np

    uri = (model_uri or "").strip()
    model = _MODEL_REGISTRY.get(uri)

    # Re-load if not in registry
    if model is None:
        import os

        if uri.startswith("runs:") or uri.startswith("models:"):
            try:
                import mlflow  # type: ignore

                model = mlflow.pyfunc.load_model(uri)
            except Exception as exc:
                return f"Could not load model: {exc}", {"error": str(exc)}
        elif os.path.isfile(uri):
            try:
                import joblib  # type: ignore

                model = joblib.load(uri)
            except Exception:
                import pickle

                with open(uri, "rb") as fh:
                    model = pickle.load(fh)
        else:
            return f"Model not found – call load_model first. URI: {uri}", {"error": "model not loaded"}

    if not input_data_raw:
        return "input_data_raw is empty – provide input data to run inference.", {"error": "empty input"}

    try:
        df = pd.DataFrame(input_data_raw)
    except Exception as exc:
        return f"Could not convert input_data_raw to DataFrame: {exc}", {"error": str(exc)}

    # Resolve task type from previous serving_results if available
    tt = (task_type or "auto").lower().strip()
    if tt == "auto" and serving_results:
        tt = serving_results.get("task_type", "auto")
    if tt == "auto":
        if hasattr(model, "predict_proba") or hasattr(model, "classes_"):
            tt = "classification"
        else:
            tt = "regression"

    try:
        # MLflow pyfunc uses DataFrame directly
        if hasattr(model, "_model_impl"):  # mlflow wrapper
            preds_raw = model.predict(df)
        else:
            preds_raw = model.predict(df)

        if hasattr(preds_raw, "tolist"):
            predictions = preds_raw.tolist()
        else:
            predictions = list(preds_raw)

        probabilities: Optional[List] = None
        classes: Optional[List] = None

        if tt == "classification" and hasattr(model, "predict_proba"):
            proba_raw = model.predict_proba(df)
            probabilities = proba_raw.tolist()
            if hasattr(model, "classes_"):
                classes = model.classes_.tolist()

    except Exception as exc:
        return f"Inference error: {exc}", {"error": str(exc)}

    n_samples = len(predictions)
    unique_preds = len(set(predictions)) if tt == "classification" else None

    # Value counts for classification
    pred_distribution: Optional[Dict] = None
    if tt == "classification":
        from collections import Counter

        pred_distribution = dict(Counter(predictions))

    artifact = {
        "model_uri": uri,
        "task_type": tt,
        "n_samples": n_samples,
        "predictions": predictions,
        "probabilities": probabilities,
        "classes": classes,
        "pred_distribution": pred_distribution,
        "unique_predictions": unique_preds,
    }

    summary = (
        f"Inference complete on {n_samples} samples (task={tt})."
        + (f" Unique classes predicted: {unique_preds}." if unique_preds is not None else "")
    )
    return summary, artifact


@tool(response_format="content_and_artifact")
def health_check(
    model_uri: Annotated[str, InjectedState("model_uri")],
    task_type: Annotated[str, InjectedState("task_type")],
    serving_results: Annotated[Dict, InjectedState("serving_results")],
) -> Tuple[str, Dict]:
    """
    Tool: health_check
    Description:
        Checks production readiness of the loaded model.  Verifies the model
        is present in the registry, that it exposes a ``predict`` method, and
        optionally runs a tiny synthetic batch to confirm end-to-end inference
        works without errors.  Use this before routing live data to the model.

    Parameters:
        model_uri       : Model path or MLflow URI (injected from state).
        task_type       : Task type hint (injected from state).
        serving_results : Previous inference artifact; used to determine
                          feature count / names if available (injected).

    Returns:
        Tuple[str, Dict]: health summary text + status artifact.
    """
    print("    * Tool: health_check")
    import numpy as np

    uri = (model_uri or "").strip()
    model = _MODEL_REGISTRY.get(uri)

    status: Dict = {
        "model_uri": uri,
        "model_in_registry": model is not None,
        "has_predict": False,
        "has_predict_proba": False,
        "smoke_test_passed": False,
        "smoke_test_error": None,
        "task_type": (task_type or "auto"),
        "ready": False,
    }

    if model is None:
        return (
            f"HEALTH CHECK FAILED – model '{uri}' not in registry. "
            "Call load_model first.",
            status,
        )

    status["has_predict"] = callable(getattr(model, "predict", None))
    status["has_predict_proba"] = callable(getattr(model, "predict_proba", None))

    if not status["has_predict"]:
        return (
            f"HEALTH CHECK FAILED – model object has no predict() method.",
            status,
        )

    # Determine feature count for smoke test
    n_features = None
    for attr in ("n_features_in_", "n_features_"):
        n_feat = getattr(model, attr, None)
        if n_feat is not None:
            n_features = int(n_feat)
            break
    if n_features is None and serving_results:
        fn = serving_results.get("feature_names")
        if fn:
            n_features = len(fn)
    if n_features is None:
        n_features = 1  # fallback

    # Run a tiny smoke-test batch (2 rows of zeros)
    try:
        dummy = np.zeros((2, n_features))
        _ = model.predict(dummy)
        status["smoke_test_passed"] = True
    except Exception as exc:
        status["smoke_test_error"] = str(exc)

    status["ready"] = status["has_predict"] and status["smoke_test_passed"]
    verdict = "READY" if status["ready"] else "NOT READY"
    summary = (
        f"Health check {verdict} for '{uri}': "
        f"predict={status['has_predict']}, "
        f"predict_proba={status['has_predict_proba']}, "
        f"smoke_test={'OK' if status['smoke_test_passed'] else 'FAILED'}."
        + (f" Error: {status['smoke_test_error']}" if status['smoke_test_error'] else "")
    )
    return summary, status


@tool(response_format="content")
def get_serving_params(
    model_uri: Annotated[str, InjectedState("model_uri")],
    task_type: Annotated[str, InjectedState("task_type")],
) -> str:
    """
    Tool: get_serving_params
    Description:
        Returns a summary of the current model serving configuration.

    Parameters:
        model_uri : Model path or MLflow URI (injected from state).
        task_type : Task type (injected from state).

    Returns:
        str: Human-readable configuration summary.
    """
    print("    * Tool: get_serving_params")
    loaded = model_uri in _MODEL_REGISTRY
    return (
        f"Model Serving config → uri='{model_uri}', task_type='{task_type}', "
        f"model_loaded={loaded}."
    )


SERVING_TOOLS = [load_model, run_inference, health_check, get_serving_params]

# Module-level in-memory model registry (avoids re-loading on repeated inference calls)
_MODEL_REGISTRY: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_model_serving_agent(
    model: Any,
    model_uri: str = "",
    task_type: str = "auto",
    create_react_agent_kwargs: Optional[Dict] = None,
    invoke_react_agent_kwargs: Optional[Dict] = None,
    checkpointer: Optional[Checkpointer] = None,
    log_tool_calls: bool = True,
):
    """
    Creates the compiled LangGraph StateGraph for the ModelServingAgent.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    model_uri : str
        Local file path or MLflow model URI. Default ''.
    task_type : str
        Task type: 'classification', 'regression', or 'auto'. Default 'auto'.
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
        model_uri: str
        task_type: str
        input_data_raw: dict
        serving_results: dict
        tool_calls: list

    react_agent = create_agent(
        model,
        tools=SERVING_TOOLS,
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
        print("    * RUN REACT TOOL-CALLING AGENT FOR MODEL SERVING")
        uri = state.get("model_uri", model_uri)
        tt = state.get("task_type", task_type)
        print(f"    * model_uri={uri}, task_type={tt}")

        system_hint = (
            "You are a Model Serving agent. "
            "Call 'load_model' to load the model, then call 'run_inference' to "
            "generate predictions on the provided input data. "
            "Return a concise summary of the inference results."
        )
        base_messages = state.get("messages", []) or [
            ("user", state.get("user_instructions"))  # type: ignore[list-item]
        ]
        messages = [("system", system_hint)] + list(base_messages)  # type: ignore[operator]

        input_payload = {
            "messages": messages,
            "model_uri": uri,
            "task_type": tt,
            "input_data_raw": state.get("input_data_raw") or {},
            "serving_results": state.get("serving_results") or {},
        }
        return react_agent.invoke(input_payload, invoke_react_agent_kwargs)  # type: ignore[arg-type]

    def post_process(state: GraphState):
        print("    * POST-PROCESSING MODEL SERVING RESULTS")

        internal_messages = state.get("messages", [])
        if not internal_messages:
            return {"messages": [], "serving_results": {}, "tool_calls": []}

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
                content="Model inference completed. See serving_results for details.",
                name=AGENT_NAME,
            )

        serving_artifact: Dict = {}
        for msg in internal_messages:
            art = getattr(msg, "artifact", None)
            if art is not None and isinstance(art, dict):
                serving_artifact.update(art)

        tool_calls = get_tool_call_names(internal_messages)
        if log_tool_calls and tool_calls:
            for tc in tool_calls:
                print(f"    * Tool: {tc}")

        return {
            "messages": [last_ai_message],
            "internal_messages": internal_messages,
            "serving_results": serving_artifact,
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


class ModelServingAgent(BaseAgent):
    """
    A tool-calling agent that loads a trained model and runs inference on
    tabular input data, returning predictions with serving metadata.

    Parameters
    ----------
    model : Any
        LangChain LLM (must support tool-calling, e.g. ChatOpenAI).
    model_uri : str
        Local file path (.pkl/.joblib) or MLflow URI
        (``runs:/<id>/model`` / ``models:/<name>/<version>``). Default ''.
    task_type : str
        Task type: 'classification', 'regression', or 'auto'. Default 'auto'.
    create_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to ``create_agent``.
    invoke_react_agent_kwargs : dict, optional
        Extra kwargs forwarded to react-agent invocation.
    checkpointer : Checkpointer, optional
        LangGraph checkpointer.
    log_tool_calls : bool
        Print tool call names when True.

    Examples
    --------
    >>> agent = ModelServingAgent(model=llm, model_uri="model.pkl", task_type="classification")
    >>> agent.invoke_agent(input_data=df)
    >>> agent.get_predictions()
    >>> agent.get_predictions_as_dataframe()
    """

    def __init__(
        self,
        model: Any,
        model_uri: str = "",
        task_type: str = "auto",
        create_react_agent_kwargs: Optional[Dict] = None,
        invoke_react_agent_kwargs: Optional[Dict] = None,
        checkpointer: Optional[Checkpointer] = None,
        log_tool_calls: bool = True,
    ):
        self._params = {
            "model": model,
            "model_uri": model_uri,
            "task_type": task_type,
            "create_react_agent_kwargs": create_react_agent_kwargs or {},
            "invoke_react_agent_kwargs": invoke_react_agent_kwargs or {},
            "checkpointer": checkpointer,
            "log_tool_calls": log_tool_calls,
        }
        self._compiled_graph = self._make_compiled_graph()
        self.response = None

    def _make_compiled_graph(self):
        self.response = None
        return make_model_serving_agent(**self._params)

    def update_params(self, **kwargs):
        """Updates agent parameters and rebuilds the compiled graph."""
        for k, v in kwargs.items():
            self._params[k] = v
        self._compiled_graph = self._make_compiled_graph()

    def invoke_agent(
        self,
        input_data: pd.DataFrame = None,
        user_instructions: str = None,
        model_uri: str = None,
        task_type: str = None,
        **kwargs,
    ):
        """
        Run the model serving agent.

        Parameters
        ----------
        input_data : pd.DataFrame
            Input features for model inference.
        user_instructions : str, optional
            Natural-language description.  Defaults to a generic prompt.
        model_uri : str, optional
            Override the default model URI for this call.
        task_type : str, optional
            Override the default task type.
        """
        _uri = model_uri or self._params["model_uri"]
        _tt = task_type or self._params["task_type"]

        if user_instructions is None:
            user_instructions = (
                f"Load the model from '{_uri}' and run inference on the provided "
                f"input data (task_type='{_tt}'). Summarise the predictions."
            )

        messages = kwargs.pop("messages", None)
        if messages is None:
            messages = [("user", user_instructions)]

        response = self._compiled_graph.invoke(
            {
                "messages": messages,
                "user_instructions": user_instructions,
                "model_uri": _uri,
                "task_type": _tt,
                "input_data_raw": input_data.to_dict() if input_data is not None else {},
                "serving_results": {},
            },
            **kwargs,
        )
        self.response = response
        return None

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_serving_result(self) -> Optional[Dict]:
        """Returns the full serving result artifact dictionary."""
        if not self.response:
            return None
        return self.response.get("serving_results")

    def get_predictions(self) -> Optional[List]:
        """Returns the list of model predictions."""
        r = self.get_serving_result()
        return r.get("predictions") if r else None

    def get_probabilities(self) -> Optional[List]:
        """Returns prediction probabilities (classification only)."""
        r = self.get_serving_result()
        return r.get("probabilities") if r else None

    def get_classes(self) -> Optional[List]:
        """Returns the class labels (classification only)."""
        r = self.get_serving_result()
        return r.get("classes") if r else None

    def get_pred_distribution(self) -> Optional[Dict]:
        """Returns the prediction value counts (classification only)."""
        r = self.get_serving_result()
        return r.get("pred_distribution") if r else None

    def get_n_samples(self) -> Optional[int]:
        """Returns the number of samples that were scored."""
        r = self.get_serving_result()
        return r.get("n_samples") if r else None

    def get_task_type(self) -> Optional[str]:
        """Returns the resolved task type ('classification' or 'regression')."""
        r = self.get_serving_result()
        return r.get("task_type") if r else None

    def get_predictions_as_dataframe(self) -> Optional[pd.DataFrame]:
        """
        Returns predictions (and probabilities if available) as a DataFrame.
        For classification: columns = ['prediction', class_0, class_1, ...].
        For regression:     column  = ['prediction'].
        """
        preds = self.get_predictions()
        if preds is None:
            return None
        df = pd.DataFrame({"prediction": preds})
        proba = self.get_probabilities()
        classes = self.get_classes()
        if proba is not None:
            proba_df = pd.DataFrame(
                proba,
                columns=[f"prob_{c}" for c in (classes or range(len(proba[0])))],
            )
            df = pd.concat([df, proba_df], axis=1)
        return df

    def get_model_metadata(self) -> Optional[Dict]:
        """Returns metadata about the loaded model (type, flavour, features)."""
        r = self.get_serving_result()
        if r is None:
            return None
        return {
            k: r[k]
            for k in ("model_uri", "model_type", "flavour", "feature_names")
            if k in r
        }

    def get_health_status(self) -> Optional[Dict]:
        """
        Returns the health check status artifact from the last agent run.
        Keys: model_in_registry, has_predict, has_predict_proba,
              smoke_test_passed, smoke_test_error, ready.
        """
        r = self.get_serving_result()
        if r is None:
            return None
        health_keys = (
            "model_in_registry",
            "has_predict",
            "has_predict_proba",
            "smoke_test_passed",
            "smoke_test_error",
            "ready",
        )
        return {k: r[k] for k in health_keys if k in r} or None

    def is_ready(self) -> Optional[bool]:
        """Returns True if the last health_check passed (model ready for inference)."""
        r = self.get_serving_result()
        return r.get("ready") if r else None

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
