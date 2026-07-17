from __future__ import annotations

"""Anomaly detection tools for the AI Data Science Team.

This module provides tools for detecting anomalies and outliers in data
using various algorithms including Isolation Forest, Local Outlier Factor,
and ensemble methods.

Tools
-----
- isolation_forest_detect: Detect anomalies using Isolation Forest
- lof_detect: Detect anomalies using Local Outlier Factor
- hbos_detect: Detect anomalies using Histogram-based Outlier Score
- copod_detect: Detect anomalies using Copula-based Outlier Detection
- ensemble_detect: Detect anomalies using ensemble voting
"""

from typing import List, Optional, Union  # noqa: E402, F401

import numpy as np  # noqa: E402, F401
import pandas as pd  # noqa: E402, F401

from ai_data_science_team.tool_registry import (  # noqa: E402, F401
    ToolParameter,
    register_tool,
)


@register_tool(
    name="isolation_forest_detect",
    description="Detect anomalies using Isolation Forest algorithm.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "contamination": ToolParameter(type="number", description="Expected proportion of outliers (0-0.5)", required=False, default=0.1),
        "n_estimators": ToolParameter(type="integer", description="Number of trees", required=False, default=100),
        "random_state": ToolParameter(type="integer", description="Random seed", required=False, default=42),
    },
    returns="Dict with anomaly indices, scores, and summary",
    namespace="core.anomaly",
    capabilities=["anomaly", "outlier", "isolation_forest"],
    cost_tier="medium",
)
def isolation_forest_detect(
    data: Union[pd.DataFrame, dict],
    contamination: float = 0.1,
    n_estimators: int = 100,
    random_state: int = 42,
) -> dict:
    """Detect anomalies using Isolation Forest.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    contamination : float
        Expected proportion of outliers (0-0.5).
    n_estimators : int
        Number of trees.
    random_state : int
        Random seed.

    Returns
    -------
    dict
        {anomaly_indices: list, scores: list, summary: str}
    """
    from sklearn.ensemble import IsolationForest  # noqa: E402, F401
    from sklearn.preprocessing import StandardScaler  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return {"anomaly_indices": [], "scores": [], "summary": "No numeric columns found"}

    X = df[numeric_cols].fillna(0)
    X_scaled = StandardScaler().fit_transform(X)

    model = IsolationForest(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
    )
    predictions = model.fit_predict(X_scaled)
    scores = model.score_samples(X_scaled)

    anomaly_mask = predictions == -1
    anomaly_indices = df.index[anomaly_mask].tolist()
    anomaly_scores = scores[anomaly_mask].tolist()

    summary = f"Isolation Forest detected {len(anomaly_indices)} anomalies ({len(anomaly_indices)/len(df)*100:.1f}% of data)"

    return {
        "anomaly_indices": anomaly_indices,
        "scores": anomaly_scores,
        "predictions": predictions.tolist(),
        "summary": summary,
    }


@register_tool(
    name="lof_detect",
    description="Detect anomalies using Local Outlier Factor algorithm.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "n_neighbors": ToolParameter(type="integer", description="Number of neighbors", required=False, default=20),
        "contamination": ToolParameter(type="number", description="Expected proportion of outliers (0-0.5)", required=False, default=0.1),
    },
    returns="Dict with anomaly indices, scores, and summary",
    namespace="core.anomaly",
    capabilities=["anomaly", "outlier", "lof"],
    cost_tier="medium",
)
def lof_detect(
    data: Union[pd.DataFrame, dict],
    n_neighbors: int = 20,
    contamination: float = 0.1,
) -> dict:
    """Detect anomalies using Local Outlier Factor.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    n_neighbors : int
        Number of neighbors.
    contamination : float
        Expected proportion of outliers (0-0.5).

    Returns
    -------
    dict
        {anomaly_indices: list, scores: list, summary: str}
    """
    from sklearn.neighbors import LocalOutlierFactor  # noqa: E402, F401
    from sklearn.preprocessing import StandardScaler  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return {"anomaly_indices": [], "scores": [], "summary": "No numeric columns found"}

    X = df[numeric_cols].fillna(0)
    X_scaled = StandardScaler().fit_transform(X)

    model = LocalOutlierFactor(
        n_neighbors=n_neighbors,
        contamination=contamination,
    )
    predictions = model.fit_predict(X_scaled)
    scores = model.negative_outlier_factor_

    anomaly_mask = predictions == -1
    anomaly_indices = df.index[anomaly_mask].tolist()
    anomaly_scores = scores[anomaly_mask].tolist()

    summary = f"LOF detected {len(anomaly_indices)} anomalies ({len(anomaly_indices)/len(df)*100:.1f}% of data)"

    return {
        "anomaly_indices": anomaly_indices,
        "scores": anomaly_scores,
        "predictions": predictions.tolist(),
        "summary": summary,
    }


@register_tool(
    name="hbos_detect",
    description="Detect anomalies using Histogram-based Outlier Score (requires PyOD).",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "contamination": ToolParameter(type="number", description="Expected proportion of outliers (0-0.5)", required=False, default=0.1),
        "n_bins": ToolParameter(type="integer", description="Number of bins", required=False, default=10),
    },
    returns="Dict with anomaly indices, scores, and summary",
    namespace="core.anomaly",
    capabilities=["anomaly", "outlier", "hbos"],
    cost_tier="medium",
)
def hbos_detect(
    data: Union[pd.DataFrame, dict],
    contamination: float = 0.1,
    n_bins: int = 10,
) -> dict:
    """Detect anomalies using Histogram-based Outlier Score.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    contamination : float
        Expected proportion of outliers (0-0.5).
    n_bins : int
        Number of bins.

    Returns
    -------
    dict
        {anomaly_indices: list, scores: list, summary: str}
    """
    from sklearn.preprocessing import StandardScaler  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return {"anomaly_indices": [], "scores": [], "summary": "No numeric columns found"}

    X = df[numeric_cols].fillna(0)
    X_scaled = StandardScaler().fit_transform(X)

    try:
        from pyod.models.hbos import HBOS  # noqa: E402, F401

        model = HBOS(contamination=contamination, n_bins=n_bins)
        model.fit(X_scaled)
        predictions = model.predict(X_scaled)
        scores = model.decision_scores_

        anomaly_mask = predictions == 1
        anomaly_indices = df.index[anomaly_mask].tolist()
        anomaly_scores = scores[anomaly_mask].tolist()

        summary = f"HBOS detected {len(anomaly_indices)} anomalies ({len(anomaly_indices)/len(df)*100:.1f}% of data)"
    except ImportError:
        return isolation_forest_detect(data, contamination=contamination)

    return {
        "anomaly_indices": anomaly_indices,
        "scores": anomaly_scores,
        "predictions": predictions.tolist(),
        "summary": summary,
    }


@register_tool(
    name="copod_detect",
    description="Detect anomalies using Copula-based Outlier Detection (requires PyOD).",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "contamination": ToolParameter(type="number", description="Expected proportion of outliers (0-0.5)", required=False, default=0.1),
    },
    returns="Dict with anomaly indices, scores, and summary",
    namespace="core.anomaly",
    capabilities=["anomaly", "outlier", "copod"],
    cost_tier="medium",
)
def copod_detect(
    data: Union[pd.DataFrame, dict],
    contamination: float = 0.1,
) -> dict:
    """Detect anomalies using Copula-based Outlier Detection.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    contamination : float
        Expected proportion of outliers (0-0.5).

    Returns
    -------
    dict
        {anomaly_indices: list, scores: list, summary: str}
    """
    from sklearn.preprocessing import StandardScaler  # noqa: E402, F401

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_cols:
        return {"anomaly_indices": [], "scores": [], "summary": "No numeric columns found"}

    X = df[numeric_cols].fillna(0)
    X_scaled = StandardScaler().fit_transform(X)

    try:
        from pyod.models.copod import COPOD  # noqa: E402, F401

        model = COPOD(contamination=contamination)
        model.fit(X_scaled)
        predictions = model.predict(X_scaled)
        scores = model.decision_scores_

        anomaly_mask = predictions == 1
        anomaly_indices = df.index[anomaly_mask].tolist()
        anomaly_scores = scores[anomaly_mask].tolist()

        summary = f"COPOD detected {len(anomaly_indices)} anomalies ({len(anomaly_indices)/len(df)*100:.1f}% of data)"
    except ImportError:
        return isolation_forest_detect(data, contamination=contamination)

    return {
        "anomaly_indices": anomaly_indices,
        "scores": anomaly_scores,
        "predictions": predictions.tolist(),
        "summary": summary,
    }


@register_tool(
    name="ensemble_detect",
    description="Detect anomalies using ensemble voting of multiple algorithms.",
    parameters={
        "data": ToolParameter(type="object", description="Input DataFrame as dict", required=True),
        "contamination": ToolParameter(type="number", description="Expected proportion of outliers (0-0.5)", required=False, default=0.1),
        "methods": ToolParameter(type="array", description="Methods to ensemble: isolation_forest, lof", required=False),
    },
    returns="Dict with anomaly indices, scores, and summary",
    namespace="core.anomaly",
    capabilities=["anomaly", "outlier", "ensemble"],
    cost_tier="high",
)
def ensemble_detect(
    data: Union[pd.DataFrame, dict],
    contamination: float = 0.1,
    methods: Optional[List[str]] = None,
) -> dict:
    """Detect anomalies using ensemble voting.

    Parameters
    ----------
    data : DataFrame or dict
        Input data.
    contamination : float
        Expected proportion of outliers (0-0.5).
    methods : List[str], optional
        Methods to ensemble. Defaults to ['isolation_forest', 'lof'].

    Returns
    -------
    dict
        {anomaly_indices: list, scores: list, summary: str}
    """

    df = pd.DataFrame(data) if isinstance(data, dict) else data

    if methods is None:
        methods = ["isolation_forest", "lof"]

    all_predictions = []

    for method in methods:
        if method == "isolation_forest":
            result = isolation_forest_detect(df, contamination=contamination)
        elif method == "lof":
            result = lof_detect(df, contamination=contamination)
        elif method == "hbos":
            result = hbos_detect(df, contamination=contamination)
        elif method == "copod":
            result = copod_detect(df, contamination=contamination)
        else:
            continue

        predictions = result.get("predictions", [])
        if predictions:
            all_predictions.append([1 if p == -1 or p == 1 else 0 for p in predictions])

    if not all_predictions:
        return {"anomaly_indices": [], "scores": [], "summary": "No valid methods"}

    all_predictions = np.array(all_predictions)
    votes = all_predictions.sum(axis=0)
    threshold = len(methods) / 2

    anomaly_mask = votes >= threshold
    anomaly_indices = df.index[anomaly_mask].tolist()

    summary = f"Ensemble ({', '.join(methods)}) detected {len(anomaly_indices)} anomalies ({len(anomaly_indices)/len(df)*100:.1f}% of data)"

    return {
        "anomaly_indices": anomaly_indices,
        "votes": votes.tolist(),
        "summary": summary,
    }


ANOMALY_TOOLS = [
    "isolation_forest_detect",
    "lof_detect",
    "hbos_detect",
    "copod_detect",
    "ensemble_detect",
]


__all__ = [
    "isolation_forest_detect",
    "lof_detect",
    "hbos_detect",
    "copod_detect",
    "ensemble_detect",
    "ANOMALY_TOOLS",
]
