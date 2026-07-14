"""Clustering and segmentation tools (M14).

All tools use *lazy imports* so that heavy optional dependencies
(scikit-learn, matplotlib) do not break the import chain when they are not
installed.

Available tools
---------------
run_kmeans              Fit K-Means; returns cluster labels + centroids + metrics.
run_dbscan              Fit DBSCAN; returns cluster labels + core-point count.
reduce_pca              PCA dimensionality reduction + explained-variance report.
reduce_tsne             t-SNE dimensionality reduction (2-D or 3-D).
compute_cluster_profile Per-cluster mean / std / size / share statistics.
compute_silhouette      Silhouette score + per-cluster silhouette values.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from langchain.tools import tool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# K-Means clustering
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def run_kmeans(
    data: List[List[float]],
    n_clusters: int = 3,
    feature_names: Optional[List[str]] = None,
    max_iter: int = 300,
    random_state: int = 42,
    n_init: int = 10,
) -> tuple[str, Dict[str, Any]]:
    """Fit K-Means clustering on the provided data matrix.

    Parameters
    ----------
    data          : 2-D list of shape (n_samples, n_features).
    n_clusters    : Number of clusters to form.
    feature_names : Optional column labels for display.
    max_iter      : Maximum number of K-Means iterations.
    random_state  : Random seed for reproducibility.
    n_init        : Number of times K-Means is run with different centroid seeds.

    Returns a textual summary + artifact dict with keys:
        labels (list[int]), centroids (list[list[float]]),
        inertia (float), silhouette_score (float | None),
        n_clusters (int), feature_names (list[str]),
        cluster_sizes (dict), cluster_share (dict).
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
    except ImportError:
        raise ImportError("pip install scikit-learn")

    X = np.array(data, dtype=float)
    n_samples, n_features = X.shape

    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    k_eff = min(n_clusters, n_samples - 1)
    km = KMeans(
        n_clusters=k_eff,
        max_iter=max_iter,
        random_state=random_state,
        n_init=n_init,
    )
    labels = km.fit_predict(X).tolist()

    # Silhouette score requires ≥ 2 clusters and ≥ 2 samples per cluster
    sil: Optional[float] = None
    if k_eff >= 2 and len(set(labels)) >= 2:
        try:
            sil = round(float(silhouette_score(X, labels)), 4)
        except Exception as exc:
            logger.warning("silhouette_score failed for k=%d: %s", k, exc)

    sizes = {int(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}
    share = {str(k): round(v / n_samples, 4) for k, v in sizes.items()}

    artifact: Dict[str, Any] = {
        "labels": labels,
        "centroids": km.cluster_centers_.tolist(),
        "inertia": round(float(km.inertia_), 4),
        "silhouette_score": sil,
        "n_clusters": k_eff,
        "feature_names": feature_names,
        "cluster_sizes": {str(k): v for k, v in sizes.items()},
        "cluster_share": share,
    }

    summary_lines = [
        f"K-Means completed — {k_eff} clusters, {n_samples} samples.",
        f"Inertia: {artifact['inertia']}",
        f"Silhouette score: {sil if sil is not None else 'N/A (need ≥ 2 clusters with ≥ 2 samples)'}",
        "Cluster sizes: " + ", ".join(f"Cluster {k}: {v}" for k, v in sizes.items()),
    ]
    return "\n".join(summary_lines), artifact


# ---------------------------------------------------------------------------
# DBSCAN clustering
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def run_dbscan(
    data: List[List[float]],
    eps: float = 0.5,
    min_samples: int = 5,
    feature_names: Optional[List[str]] = None,
    metric: str = "euclidean",
) -> tuple[str, Dict[str, Any]]:
    """Fit DBSCAN density-based clustering.

    Parameters
    ----------
    data         : 2-D list of shape (n_samples, n_features).
    eps          : Maximum distance between two samples to be considered neighbours.
    min_samples  : Minimum samples in a neighbourhood to form a core point.
    feature_names: Optional column labels.
    metric       : Distance metric ('euclidean', 'manhattan', etc.).

    Returns a textual summary + artifact dict with keys:
        labels (list[int]),   noise_count (int),
        n_clusters (int),     cluster_sizes (dict),
        core_sample_count (int), silhouette_score (float | None).
    """
    try:
        from sklearn.cluster import DBSCAN
        from sklearn.metrics import silhouette_score
    except ImportError:
        raise ImportError("pip install scikit-learn")

    X = np.array(data, dtype=float)
    n_samples, n_features = X.shape

    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    db = DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
    labels = db.fit_predict(X).tolist()

    unique_labels = set(labels)
    n_clusters = len(unique_labels - {-1})
    noise_count = int(labels.count(-1))
    core_count = int(len(db.core_sample_indices_))

    sizes: Dict[str, int] = {}
    for lab in unique_labels:
        key = "noise" if lab == -1 else str(lab)
        sizes[key] = int(labels.count(lab))

    sil: Optional[float] = None
    if n_clusters >= 2:
        non_noise_mask = np.array(labels) != -1
        if non_noise_mask.sum() >= 2:
            try:
                sil = round(float(silhouette_score(X[non_noise_mask], np.array(labels)[non_noise_mask])), 4)
            except Exception as exc:
                logger.warning("silhouette_score failed for DBSCAN: %s", exc)

    artifact: Dict[str, Any] = {
        "labels": labels,
        "n_clusters": n_clusters,
        "noise_count": noise_count,
        "core_sample_count": core_count,
        "cluster_sizes": sizes,
        "silhouette_score": sil,
        "eps": eps,
        "min_samples": min_samples,
        "feature_names": feature_names,
    }

    summary_lines = [
        f"DBSCAN completed — {n_clusters} clusters, {noise_count} noise points.",
        f"Core samples: {core_count}  |  eps={eps}  |  min_samples={min_samples}",
        f"Silhouette score: {sil if sil is not None else 'N/A'}",
        "Cluster sizes: " + ", ".join(f"{k}: {v}" for k, v in sizes.items()),
    ]
    return "\n".join(summary_lines), artifact


# ---------------------------------------------------------------------------
# PCA dimensionality reduction
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def reduce_pca(
    data: List[List[float]],
    n_components: int = 2,
    feature_names: Optional[List[str]] = None,
    whiten: bool = False,
    random_state: int = 42,
) -> tuple[str, Dict[str, Any]]:
    """Apply Principal Component Analysis (PCA) dimensionality reduction.

    Parameters
    ----------
    data          : 2-D list of shape (n_samples, n_features).
    n_components  : Number of principal components to retain.
    feature_names : Optional column labels for the original features.
    whiten        : Whether to whiten the components.
    random_state  : Random seed.

    Returns a textual summary + artifact dict with keys:
        transformed (list[list[float]]),
        explained_variance_ratio (list[float]),
        cumulative_variance (float),
        n_components (int),
        component_loadings (list[list[float]]),
        feature_names (list[str]).
    """
    try:
        from sklearn.decomposition import PCA
    except ImportError:
        raise ImportError("pip install scikit-learn")

    X = np.array(data, dtype=float)
    n_samples, n_features = X.shape

    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    n_comp_eff = min(n_components, n_samples, n_features)
    pca = PCA(n_components=n_comp_eff, whiten=whiten, random_state=random_state)
    X_transformed = pca.fit_transform(X)

    evr = [round(float(v), 6) for v in pca.explained_variance_ratio_]
    cumvar = round(float(sum(evr)), 6)

    artifact: Dict[str, Any] = {
        "transformed": X_transformed.tolist(),
        "explained_variance_ratio": evr,
        "cumulative_variance": cumvar,
        "n_components": n_comp_eff,
        "component_loadings": pca.components_.tolist(),
        "feature_names": feature_names,
    }

    summary_lines = [
        f"PCA completed — {n_comp_eff} components from {n_features} features.",
        "Explained variance per component: "
        + ", ".join(f"PC{i+1}: {v:.1%}" for i, v in enumerate(evr)),
        f"Cumulative explained variance: {cumvar:.1%}",
    ]
    return "\n".join(summary_lines), artifact


# ---------------------------------------------------------------------------
# t-SNE dimensionality reduction
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def reduce_tsne(
    data: List[List[float]],
    n_components: int = 2,
    perplexity: float = 30.0,
    learning_rate: float = 200.0,
    max_iter: int = 1000,
    feature_names: Optional[List[str]] = None,
    random_state: int = 42,
) -> tuple[str, Dict[str, Any]]:
    """Apply t-SNE dimensionality reduction for non-linear visualisation.

    Parameters
    ----------
    data          : 2-D list of shape (n_samples, n_features).
    n_components  : Target dimensions (typically 2 or 3).
    perplexity    : Perplexity hyperparameter (5–50 is typical).
    learning_rate : Learning rate for t-SNE optimisation.
    max_iter      : Maximum number of optimisation iterations.
    feature_names : Optional column labels for original features.
    random_state  : Random seed.

    Returns a textual summary + artifact dict with keys:
        transformed (list[list[float]]),
        n_components (int),
        kl_divergence (float),
        n_iter (int),
        feature_names (list[str]).
    """
    try:
        from sklearn.manifold import TSNE
    except ImportError:
        raise ImportError("pip install scikit-learn")

    X = np.array(data, dtype=float)
    n_samples, n_features = X.shape

    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    perp_eff = min(perplexity, (n_samples - 1) / 3.0)
    tsne = TSNE(
        n_components=n_components,
        perplexity=perp_eff,
        learning_rate=learning_rate,
        max_iter=max_iter,
        random_state=random_state,
    )
    X_transformed = tsne.fit_transform(X)

    artifact: Dict[str, Any] = {
        "transformed": X_transformed.tolist(),
        "n_components": n_components,
        "kl_divergence": round(float(tsne.kl_divergence_), 6),
        "n_iter": int(tsne.n_iter_),
        "perplexity_used": round(perp_eff, 2),
        "feature_names": feature_names,
    }

    summary_lines = [
        f"t-SNE completed — {n_samples} samples → {n_components}-D embedding.",
        f"KL divergence: {artifact['kl_divergence']}  |  Iterations: {artifact['n_iter']}",
        f"Perplexity used: {artifact['perplexity_used']}",
    ]
    return "\n".join(summary_lines), artifact


# ---------------------------------------------------------------------------
# Cluster profiling
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def compute_cluster_profile(
    data: List[List[float]],
    labels: List[int],
    feature_names: Optional[List[str]] = None,
) -> tuple[str, Dict[str, Any]]:
    """Compute per-cluster descriptive statistics (mean, std, size, share).

    Parameters
    ----------
    data          : 2-D list of shape (n_samples, n_features).
    labels        : Cluster label for each sample (same length as data).
    feature_names : Optional column labels.

    Returns a textual summary + artifact dict with keys:
        profiles (dict: cluster_id → {mean, std, size, share, min, max}),
        feature_names (list[str]),
        n_clusters (int),
        global_mean (list[float]).
    """
    X = np.array(data, dtype=float)
    y = np.array(labels)
    n_samples, n_features = X.shape

    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    unique_labels = sorted(set(y.tolist()))
    profiles: Dict[str, Any] = {}
    for lab in unique_labels:
        mask = y == lab
        subset = X[mask]
        key = "noise" if lab == -1 else str(lab)
        profiles[key] = {
            "size": int(mask.sum()),
            "share": round(float(mask.sum()) / n_samples, 4),
            "mean": [round(float(v), 4) for v in subset.mean(axis=0)],
            "std":  [round(float(v), 4) for v in subset.std(axis=0)],
            "min":  [round(float(v), 4) for v in subset.min(axis=0)],
            "max":  [round(float(v), 4) for v in subset.max(axis=0)],
        }

    artifact: Dict[str, Any] = {
        "profiles": profiles,
        "feature_names": feature_names,
        "n_clusters": len([k for k in unique_labels if k != -1]),
        "global_mean": [round(float(v), 4) for v in X.mean(axis=0)],
    }

    lines = ["Cluster Profile Summary:"]
    for cid, stats in profiles.items():
        lines.append(
            f"  Cluster {cid}: n={stats['size']} ({stats['share']:.1%}) — "
            + "mean=[" + ", ".join(f"{v:.3f}" for v in stats["mean"]) + "]"
        )
    return "\n".join(lines), artifact


# ---------------------------------------------------------------------------
# Silhouette score
# ---------------------------------------------------------------------------

@tool(response_format="content_and_artifact")
def compute_silhouette(
    data: List[List[float]],
    labels: List[int],
    feature_names: Optional[List[str]] = None,
    metric: str = "euclidean",
) -> tuple[str, Dict[str, Any]]:
    """Compute the overall and per-cluster silhouette scores.

    Silhouette score ranges from -1 (incorrect clustering) to +1 (dense,
    well-separated clusters). Values near 0 indicate overlapping clusters.

    Parameters
    ----------
    data          : 2-D list of shape (n_samples, n_features).
    labels        : Cluster label for each sample (-1 = noise, excluded).
    feature_names : Optional column labels.
    metric        : Distance metric.

    Returns a textual summary + artifact dict with keys:
        overall_silhouette (float | None),
        per_cluster_silhouette (dict: cluster_id → mean silhouette),
        n_valid_samples (int),
        n_clusters (int).
    """
    try:
        from sklearn.metrics import silhouette_score, silhouette_samples
    except ImportError:
        raise ImportError("pip install scikit-learn")

    X = np.array(data, dtype=float)
    y = np.array(labels)

    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(X.shape[1])]

    # Exclude noise points (label == -1)
    mask = y != -1
    X_valid = X[mask]
    y_valid = y[mask]
    n_valid = int(mask.sum())
    unique_valid = np.unique(y_valid)
    n_clusters = int(len(unique_valid))

    overall: Optional[float] = None
    per_cluster: Dict[str, float] = {}
    per_sample_silhouette: List[float] = []

    if n_clusters >= 2 and n_valid >= 2:
        try:
            overall = round(float(silhouette_score(X_valid, y_valid, metric=metric)), 4)
            sample_vals = silhouette_samples(X_valid, y_valid, metric=metric)
            per_sample_silhouette = [round(float(v), 4) for v in sample_vals]
            for lab in unique_valid:
                sub_mask = y_valid == lab
                per_cluster[str(int(lab))] = round(float(sample_vals[sub_mask].mean()), 4)
        except Exception as exc:
            logger.warning("silhouette computation failed (metric=%s): %s", metric, exc)

    artifact: Dict[str, Any] = {
        "overall_silhouette": overall,
        "per_cluster_silhouette": per_cluster,
        "n_valid_samples": n_valid,
        "n_clusters": n_clusters,
        "feature_names": feature_names,
        "metric": metric,
    }

    status = f"{overall:.4f}" if overall is not None else "N/A (need ≥ 2 clusters)"
    lines = [
        f"Silhouette analysis — {n_clusters} clusters, {n_valid} samples.",
        f"Overall silhouette score: {status}",
    ]
    if per_cluster:
        lines.append("Per-cluster silhouette: " + ", ".join(f"C{k}: {v}" for k, v in per_cluster.items()))
    return "\n".join(lines), artifact
