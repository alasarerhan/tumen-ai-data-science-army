"""e12_clustering. Deterministic clustering tools. Implements E12
— KMeans / DBSCAN / Agglomerative (hierarchical) clustering,
silhouette + Calinski-Harabasz scoring, per-cluster feature
profiling, deterministic naming seeds, segmentation template
builder.
"""

from __future__ import annotations

import os
# Apple Silicon safety: KMeans._kmeans_single_lloyd can SIGABRT on
# multi-threaded BLAS.  Pinning these env vars *before* sklearn
# import keeps thread count at 1.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from sklearn.cluster import (
    AgglomerativeClustering,
    DBSCAN,
    KMeans,
)
from sklearn.metrics import (
    calinski_harabasz_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler


VALID_ALGORITHMS = {"kmeans", "dbscan", "hierarchical"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


# ----- Inputs --------------------------------------------------------------

@dataclass
class ClusteringResult:
    run_id: str
    algorithm: str
    params: Dict[str, Any]
    labels: List[int]
    n_clusters: int
    n_noise: int
    cluster_sizes: Dict[int, int]
    metrics: Dict[str, float]
    profiles: List[Dict[str, Any]]
    naming_seeds: List[Dict[str, Any]]
    segmentation_template: Dict[str, Any]
    created_at: float


def _to_2d_array(X: Any) -> np.ndarray:
    arr = np.asarray(X, dtype=float)
    if arr.ndim != 2:
        raise ValueError(f"X must be 2-D, got shape {arr.shape}")
    return arr


def _standardize(X: np.ndarray) -> np.ndarray:
    return StandardScaler().fit_transform(X)


# ----- Clustering algorithms -----------------------------------------------

def run_kmeans(
    X: np.ndarray,
    *,
    n_clusters: int = 4,
    random_state: int = 0,
    n_init: int = 10,
) -> np.ndarray:
    if n_clusters < 1:
        raise ValueError("n_clusters must be >= 1")
    if n_clusters > len(X):
        raise ValueError(
            f"n_clusters ({n_clusters}) > n_samples ({len(X)})"
        )
    km = KMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=n_init,
    )
    return km.fit_predict(X)


def run_dbscan(
    X: np.ndarray,
    *,
    eps: float = 0.5,
    min_samples: int = 5,
) -> np.ndarray:
    if eps <= 0:
        raise ValueError("eps must be > 0")
    if min_samples < 1:
        raise ValueError("min_samples must be >= 1")
    db = DBSCAN(eps=eps, min_samples=min_samples)
    return db.fit_predict(X)


def run_hierarchical(
    X: np.ndarray,
    *,
    n_clusters: int = 4,
    linkage: str = "ward",
) -> np.ndarray:
    if n_clusters < 1:
        raise ValueError("n_clusters must be >= 1")
    if n_clusters > len(X):
        raise ValueError(
            f"n_clusters ({n_clusters}) > n_samples ({len(X)})"
        )
    if linkage not in ("ward", "complete", "average", "single"):
        raise ValueError(f"linkage must be one of ward/complete/average/single")
    ac = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage)
    return ac.fit_predict(X)


# ----- Metrics -------------------------------------------------------------

def compute_silhouette(X: np.ndarray, labels: np.ndarray) -> float:
    """Return silhouette score in [-1, 1]. Returns NaN if < 2 clusters
    or any -1 noise labels make silhouette undefined (silhouette
    raises ValueError on that case)."""
    unique = np.unique(labels)
    if len(unique) < 2:
        return float("nan")
    if len(unique) == 2 and -1 in unique:
        # 1 cluster + noise
        return float("nan")
    try:
        return float(silhouette_score(X, labels))
    except ValueError:
        return float("nan")


def compute_calinski_harabasz(X: np.ndarray, labels: np.ndarray) -> float:
    """Return CH score. NaN if fewer than 2 clusters."""
    unique = np.unique(labels)
    if len(unique) < 2:
        return float("nan")
    try:
        return float(calinski_harabasz_score(X, labels))
    except ValueError:
        return float("nan")


def cluster_sizes(labels: Sequence[int]) -> Dict[int, int]:
    sizes: Dict[int, int] = {}
    for lab in labels:
        sizes[int(lab)] = sizes.get(int(lab), 0) + 1
    return sizes


# ----- Per-cluster profiling -----------------------------------------------

def profile_clusters(
    X: np.ndarray,
    labels: Sequence[int],
    feature_names: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Per-cluster mean / std / min / max for each feature."""
    if X.ndim != 2:
        raise ValueError("X must be 2-D")
    n_features = X.shape[1]
    if feature_names is None:
        feature_names = [f"f{i}" for i in range(n_features)]
    if len(feature_names) != n_features:
        raise ValueError(
            "feature_names length must equal n_features"
        )
    labels_arr = np.asarray(labels)
    profiles: List[Dict[str, Any]] = []
    unique_labels = sorted(set(int(x) for x in labels_arr))
    for lab in unique_labels:
        mask = labels_arr == lab
        if not mask.any():
            continue
        sub = X[mask]
        feats: Dict[str, Any] = {}
        for j, fname in enumerate(feature_names):
            col = sub[:, j]
            feats[fname] = {
                "mean": float(col.mean()),
                "std": float(col.std(ddof=0)) if len(col) > 1 else 0.0,
                "min": float(col.min()),
                "max": float(col.max()),
            }
        profiles.append({
            "cluster_id": int(lab),
            "size": int(mask.sum()),
            "share": float(mask.sum() / len(labels_arr)),
            "features": feats,
        })
    return profiles


# ----- Naming seeds --------------------------------------------------------

_NAMING_TEMPLATES = [
    "cluster_{id}",
    "segment_{id}",
    "group_{id}",
    "tier_{id}",
]


def build_naming_seeds(
    profiles: Sequence[Mapping[str, Any]],
    *,
    template_prefix: str = "segment",
) -> List[Dict[str, Any]]:
    """Build deterministic naming seeds per cluster. Each entry
    carries: cluster_id, suggested_name, top_features (z-like),
    description_seed (templated string)."""
    out: List[Dict[str, Any]] = []
    for prof in profiles:
        cid = int(prof["cluster_id"])
        feats = prof.get("features", {})
        # rank features by absolute mean (proxy for discriminative
        # power in standardised space)
        ranked = sorted(
            feats.items(),
            key=lambda kv: abs(kv[1]["mean"]),
            reverse=True,
        )
        top3 = [
            {"name": k, "mean": v["mean"], "std": v["std"]}
            for k, v in ranked[:3]
        ]
        suggested_name = f"{template_prefix}_{cid}"
        # description: list top distinguishing features
        if top3:
            descr = (
                f"{suggested_name}: high in {top3[0]['name']} "
                f"({top3[0]['mean']:.2f})"
            )
            if len(top3) > 1:
                descr += f", low in {top3[-1]['name']} ({top3[-1]['mean']:.2f})"
        else:
            descr = f"{suggested_name}"
        out.append({
            "cluster_id": cid,
            "suggested_name": suggested_name,
            "top_features": top3,
            "description_seed": descr,
        })
    return out


# ----- Segmentation template ----------------------------------------------

def segmentation_template(
    profiles: Sequence[Mapping[str, Any]],
    naming_seeds: Sequence[Mapping[str, Any]],
    *,
    total_samples: int,
) -> Dict[str, Any]:
    """Build a marketing-segment-style template: each cluster becomes
    a segment with size / share / suggested_name / top features."""
    segments: List[Dict[str, Any]] = []
    by_id = {n["cluster_id"]: n for n in naming_seeds}
    for prof in profiles:
        cid = int(prof["cluster_id"])
        seed = by_id.get(cid, {})
        segments.append({
            "segment_id": cid,
            "suggested_name": seed.get("suggested_name", f"segment_{cid}"),
            "size": prof["size"],
            "share": prof["share"],
            "top_features": seed.get("top_features", []),
            "description_seed": seed.get("description_seed", ""),
        })
    return {
        "total_samples": total_samples,
        "n_segments": len(segments),
        "segments": segments,
    }


# ----- Orchestrator --------------------------------------------------------

def run_clustering(
    X: Any,
    *,
    algorithm: str = "kmeans",
    standardize: bool = True,
    feature_names: Optional[Sequence[str]] = None,
    kmeans_kwargs: Optional[Mapping[str, Any]] = None,
    dbscan_kwargs: Optional[Mapping[str, Any]] = None,
    hierarchical_kwargs: Optional[Mapping[str, Any]] = None,
    naming_prefix: str = "segment",
) -> ClusteringResult:
    if algorithm not in VALID_ALGORITHMS:
        raise ValueError(
            f"algorithm must be one of {sorted(VALID_ALGORITHMS)}"
        )
    Xarr = _to_2d_array(X)
    Xuse = _standardize(Xarr) if standardize else Xarr
    params: Dict[str, Any] = {"standardize": standardize}
    if algorithm == "kmeans":
        kw = dict(kmeans_kwargs or {})
        kw.setdefault("n_clusters", 4)
        params["n_clusters"] = kw["n_clusters"]
        params["random_state"] = kw.get("random_state", 0)
        labels = run_kmeans(Xuse, **kw)
    elif algorithm == "dbscan":
        kw = dict(dbscan_kwargs or {})
        kw.setdefault("eps", 0.5)
        kw.setdefault("min_samples", 5)
        params["eps"] = kw["eps"]
        params["min_samples"] = kw["min_samples"]
        labels = run_dbscan(Xuse, **kw)
    else:  # hierarchical
        kw = dict(hierarchical_kwargs or {})
        kw.setdefault("n_clusters", 4)
        kw.setdefault("linkage", "ward")
        params["n_clusters"] = kw["n_clusters"]
        params["linkage"] = kw["linkage"]
        labels = run_hierarchical(Xuse, **kw)
    labels_list = [int(x) for x in labels]
    sizes = cluster_sizes(labels_list)
    n_clusters_eff = sum(1 for k in sizes if k != -1)
    n_noise = sizes.get(-1, 0)
    sil = compute_silhouette(Xuse, labels)
    ch = compute_calinski_harabasz(Xuse, labels)
    profiles = profile_clusters(
        Xuse, labels_list, feature_names=feature_names,
    )
    seeds = build_naming_seeds(profiles, template_prefix=naming_prefix)
    seg_template = segmentation_template(
        profiles, seeds, total_samples=len(Xarr),
    )
    return ClusteringResult(
        run_id=_new_id(),
        algorithm=algorithm,
        params=params,
        labels=labels_list,
        n_clusters=n_clusters_eff,
        n_noise=n_noise,
        cluster_sizes=sizes,
        metrics={"silhouette": sil, "calinski_harabasz": ch},
        profiles=profiles,
        naming_seeds=seeds,
        segmentation_template=seg_template,
        created_at=_now(),
    )


def result_payload(r: ClusteringResult) -> Dict[str, Any]:
    return {
        "run_id": r.run_id,
        "algorithm": r.algorithm,
        "params": r.params,
        "n_clusters": r.n_clusters,
        "n_noise": r.n_noise,
        "cluster_sizes": r.cluster_sizes,
        "metrics": r.metrics,
        "profiles": r.profiles,
        "naming_seeds": r.naming_seeds,
        "segmentation_template": r.segmentation_template,
        "created_at": r.created_at,
    }


E12_CLUSTERING_TOOL_NAMES: List[str] = [
    "e12_run_kmeans",
    "e12_run_dbscan",
    "e12_run_hierarchical",
    "e12_compute_silhouette",
    "e12_compute_calinski_harabasz",
    "e12_profile_clusters",
    "e12_build_naming_seeds",
    "e12_segmentation_template",
    "e12_run_clustering",
    "e12_result_payload",
]
