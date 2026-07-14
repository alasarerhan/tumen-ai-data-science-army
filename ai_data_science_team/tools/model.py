"""Model serving tools for the AI Data Science Team.

This module provides tools for loading, running inference, and evaluating
machine learning models.

Tools
-----
- load_model: Load a model from file or MLflow
- predict_classification: Run classification inference
- predict_regression: Run regression inference
- evaluate_model: Calculate model metrics
"""

from __future__ import annotations

import os
from typing import Any, Union

import numpy as np
import pandas as pd

from ai_data_science_team.tool_registry import (
    ToolParameter,
    register_tool,
)


@register_tool(
    name="load_model",
    description="Load a model from local file path or MLflow URI.",
    parameters={
        "model_uri": ToolParameter(type="string", description="Model path or MLflow URI (runs:/<id>/model, models:/<name>/<version>)", required=True),
        "task_type": ToolParameter(type="string", description="Task type: classification, regression, or auto", required=False, default="auto"),
    },
    returns="Dict with model metadata",
    namespace="core.model",
    capabilities=["model", "loading", "mlflow"],
    cost_tier="low",
)
def load_model(
    model_uri: str,
    task_type: str = "auto",
) -> dict:
    """Load a model from local file path or MLflow URI.

    Parameters
    ----------
    model_uri : str
        Model path or MLflow URI.
    task_type : str
        Task type: classification, regression, or auto.

    Returns
    -------
    dict
        Model metadata including loaded model reference.
    """
    import joblib

    model = None
    model_type = None
    framework = None

    if model_uri.startswith("runs:/") or model_uri.startswith("models:/"):
        try:
            import mlflow
            model = mlflow.sklearn.load_model(model_uri)
            framework = "sklearn"
            model_type = type(model).__name__
        except ImportError:
            return {"error": "MLflow not installed", "model_uri": model_uri}
        except Exception as e:
            return {"error": str(e), "model_uri": model_uri}
    else:
        ext = os.path.splitext(model_uri)[1].lower()
        if ext in (".pkl", ".pickle", ".joblib"):
            model = joblib.load(model_uri)
            framework = "sklearn"
            model_type = type(model).__name__
        else:
            return {"error": f"Unknown file extension: {ext}", "model_uri": model_uri}

    if task_type == "auto":
        if hasattr(model, "predict_proba"):
            task_type = "classification"
        elif hasattr(model, "predict"):
            task_type = "regression"
        else:
            task_type = "unknown"

    feature_names = None
    if hasattr(model, "feature_names_in_"):
        feature_names = list(model.feature_names_in_)

    return {
        "model_uri": model_uri,
        "model_type": model_type,
        "framework": framework,
        "task_type": task_type,
        "feature_names": feature_names,
        "model_loaded": True,
    }


@register_tool(
    name="predict_classification",
    description="Run classification inference on data.",
    parameters={
        "model": ToolParameter(type="object", description="Loaded model object", required=True),
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "return_proba": ToolParameter(type="boolean", description="Return probabilities", required=False, default=False),
    },
    returns="Dict with predictions and optional probabilities",
    namespace="core.model",
    capabilities=["model", "prediction", "classification"],
    cost_tier="low",
)
def predict_classification(
    model: Any,
    data: Union[pd.DataFrame, dict],
    return_proba: bool = False,
) -> dict:
    """Run classification inference on data.

    Parameters
    ----------
    model : Any
        Loaded model object.
    data : DataFrame or dict
        Input data.
    return_proba : bool
        Return probabilities.

    Returns
    -------
    dict
        Predictions and optional probabilities.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if hasattr(model, "feature_names_in_"):
        missing = set(model.feature_names_in_) - set(df.columns)
        if missing:
            for col in missing:
                df[col] = 0
            df = df[model.feature_names_in_]

    predictions = model.predict(df.fillna(0))

    result = {
        "predictions": predictions.tolist(),
        "n_samples": len(predictions),
    }

    if return_proba and hasattr(model, "predict_proba"):
        proba = model.predict_proba(df.fillna(0))
        result["probabilities"] = proba.tolist()
        if hasattr(model, "classes_"):
            result["classes"] = list(model.classes_)

    return result


@register_tool(
    name="predict_regression",
    description="Run regression inference on data.",
    parameters={
        "model": ToolParameter(type="object", description="Loaded model object", required=True),
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
    },
    returns="Dict with predictions",
    namespace="core.model",
    capabilities=["model", "prediction", "regression"],
    cost_tier="low",
)
def predict_regression(
    model: Any,
    data: Union[pd.DataFrame, dict],
) -> dict:
    """Run regression inference on data.

    Parameters
    ----------
    model : Any
        Loaded model object.
    data : DataFrame or dict
        Input data.

    Returns
    -------
    dict
        Predictions.
    """
    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if hasattr(model, "feature_names_in_"):
        missing = set(model.feature_names_in_) - set(df.columns)
        if missing:
            for col in missing:
                df[col] = 0
            df = df[model.feature_names_in_]

    predictions = model.predict(df.fillna(0))

    return {
        "predictions": predictions.tolist(),
        "n_samples": len(predictions),
        "mean_prediction": float(np.mean(predictions)),
        "std_prediction": float(np.std(predictions)),
    }


@register_tool(
    name="evaluate_model",
    description="Evaluate model performance with metrics.",
    parameters={
        "model": ToolParameter(type="object", description="Loaded model object", required=True),
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "target": ToolParameter(type="string", description="Target column name", required=True),
        "task_type": ToolParameter(type="string", description="Task type: classification or regression", required=True),
    },
    returns="Dict with evaluation metrics",
    namespace="core.model",
    capabilities=["model", "evaluation", "metrics"],
    cost_tier="low",
)
def evaluate_model(
    model: Any,
    data: Union[pd.DataFrame, dict],
    target: str,
    task_type: str,
) -> dict:
    """Evaluate model performance with metrics.

    Parameters
    ----------
    model : Any
        Loaded model object.
    data : DataFrame or dict
        Input data with target column.
    target : str
        Target column name.
    task_type : str
        Task type: classification or regression.

    Returns
    -------
    dict
        Evaluation metrics.
    """
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        roc_auc_score,
        mean_squared_error,
        mean_absolute_error,
        r2_score,
    )

    df = pd.DataFrame(data) if isinstance(data, dict) else data.copy()

    if target not in df.columns:
        return {"error": f"Target column '{target}' not found"}

    y_true = df[target].values
    X = df.drop(columns=[target])

    if hasattr(model, "feature_names_in_"):
        missing = set(model.feature_names_in_) - set(X.columns)
        for col in missing:
            X[col] = 0
        X = X[model.feature_names_in_]

    y_pred = model.predict(X.fillna(0))

    metrics = {}

    if task_type == "classification":
        metrics["accuracy"] = float(accuracy_score(y_true, y_pred))
        metrics["precision"] = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))
        metrics["recall"] = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))
        metrics["f1"] = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

        if hasattr(model, "predict_proba"):
            try:
                y_proba = model.predict_proba(X.fillna(0))
                if y_proba.shape[1] == 2:
                    metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba[:, 1]))
            except Exception:
                pass

    elif task_type == "regression":
        metrics["mse"] = float(mean_squared_error(y_true, y_pred))
        metrics["rmse"] = float(np.sqrt(metrics["mse"]))
        metrics["mae"] = float(mean_absolute_error(y_true, y_pred))
        metrics["r2"] = float(r2_score(y_true, y_pred))

    metrics["n_samples"] = len(y_true)
    metrics["task_type"] = task_type

    return metrics


MODEL_TOOLS = [
    "load_model",
    "predict_classification",
    "predict_regression",
    "evaluate_model",
]


__all__ = [
    "load_model",
    "predict_classification",
    "predict_regression",
    "evaluate_model",
    "MODEL_TOOLS",
]
