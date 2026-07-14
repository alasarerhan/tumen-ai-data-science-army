"""Tests for E12 Clustering tool."""
from __future__ import annotations

import math

import numpy as np
import pytest

import ai_data_science_team.tools.e12_clustering as e12


def _make_blobs(n_per_cluster: int = 50, seed: int = 0) -> np.ndarray:
    """3 well-separated gaussian blobs."""
    rng = np.random.default_rng(seed)
    centers = np.array([[0.0, 0.0], [5.0, 5.0], [-5.0, 5.0]])
    parts = []
    for c in centers:
        parts.append(rng.normal(loc=c, scale=0.5, size=(n_per_cluster, 2)))
    return np.vstack(parts)


class TestInputValidation:
    def test_2d_required(self):
        with pytest.raises(ValueError):
            e12.run_clustering([1.0, 2.0, 3.0])

    def test_invalid_algorithm(self):
        X = _make_blobs(n_per_cluster=20)
        with pytest.raises(ValueError):
            e12.run_clustering(X, algorithm="kmedoids")


class TestKMeans:
    def test_finds_three_clusters(self):
        X = _make_blobs(n_per_cluster=50)
        r = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 3, "random_state": 0},
        )
        assert r.algorithm == "kmeans"
        assert r.n_clusters == 3
        assert r.n_noise == 0
        assert set(r.labels) == {0, 1, 2}
        assert sum(r.cluster_sizes.values()) == 150

    def test_silhouette_in_range(self):
        X = _make_blobs(n_per_cluster=50)
        r = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 3, "random_state": 0},
        )
        assert -1.0 <= r.metrics["silhouette"] <= 1.0
        # well-separated blobs → silhouette should be high (>0.5)
        assert r.metrics["silhouette"] > 0.5

    def test_calinski_harabasz_positive(self):
        X = _make_blobs(n_per_cluster=50)
        r = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 3, "random_state": 0},
        )
        assert r.metrics["calinski_harabasz"] > 0

    def test_n_clusters_validation(self):
        X = _make_blobs(n_per_cluster=10)
        with pytest.raises(ValueError):
            e12.run_kmeans(X, n_clusters=0)
        with pytest.raises(ValueError):
            e12.run_kmeans(X, n_clusters=100)


class TestDBSCAN:
    def test_basic(self):
        X = _make_blobs(n_per_cluster=30)
        r = e12.run_clustering(
            X, algorithm="dbscan",
            dbscan_kwargs={"eps": 0.6, "min_samples": 5},
        )
        assert r.algorithm == "dbscan"
        # DBSCAN should find ~3 clusters (well-separated)
        assert r.n_clusters >= 2

    def test_eps_validation(self):
        X = _make_blobs(n_per_cluster=10)
        with pytest.raises(ValueError):
            e12.run_dbscan(X, eps=0)
        with pytest.raises(ValueError):
            e12.run_dbscan(X, min_samples=0)


class TestHierarchical:
    def test_basic(self):
        X = _make_blobs(n_per_cluster=30)
        r = e12.run_clustering(
            X, algorithm="hierarchical",
            hierarchical_kwargs={"n_clusters": 3, "linkage": "ward"},
        )
        assert r.algorithm == "hierarchical"
        assert r.n_clusters == 3

    def test_invalid_linkage(self):
        X = _make_blobs(n_per_cluster=10)
        with pytest.raises(ValueError):
            e12.run_hierarchical(X, n_clusters=2, linkage="weird")

    def test_different_linkages(self):
        X = _make_blobs(n_per_cluster=20)
        for linkage in ("ward", "complete", "average", "single"):
            r = e12.run_clustering(
                X, algorithm="hierarchical",
                hierarchical_kwargs={"n_clusters": 3, "linkage": linkage},
            )
            assert r.n_clusters == 3


class TestClusterSizes:
    def test_sizes(self):
        labels = [0, 0, 0, 1, 1, 2]
        sizes = e12.cluster_sizes(labels)
        assert sizes == {0: 3, 1: 2, 2: 1}

    def test_noise_label(self):
        labels = [0, 0, -1, -1, 1]
        sizes = e12.cluster_sizes(labels)
        assert sizes == {0: 2, -1: 2, 1: 1}


class TestMetrics:
    def test_silhouette_single_cluster_nan(self):
        X = np.array([[0.0, 0.0], [0.1, 0.1]])
        s = e12.compute_silhouette(X, np.array([0, 0]))
        assert math.isnan(s)

    def test_calinski_harabasz_single_cluster_nan(self):
        X = np.array([[0.0, 0.0], [0.1, 0.1]])
        c = e12.compute_calinski_harabasz(X, np.array([0, 0]))
        assert math.isnan(c)


class TestProfileClusters:
    def test_basic(self):
        X = _make_blobs(n_per_cluster=30)
        labels = e12.run_kmeans(X, n_clusters=3, random_state=0)
        profiles = e12.profile_clusters(
            X, labels, feature_names=["x", "y"],
        )
        assert len(profiles) == 3
        for p in profiles:
            assert "size" in p
            assert "share" in p
            assert "x" in p["features"]
            assert "y" in p["features"]
            assert all(
                k in p["features"]["x"]
                for k in ("mean", "std", "min", "max")
            )

    def test_default_feature_names(self):
        X = _make_blobs(n_per_cluster=10)
        labels = e12.run_kmeans(X, n_clusters=2, random_state=0)
        profiles = e12.profile_clusters(X, labels)
        assert "f0" in profiles[0]["features"]
        assert "f1" in profiles[0]["features"]

    def test_feature_names_length_mismatch(self):
        X = _make_blobs(n_per_cluster=10)
        labels = e12.run_kmeans(X, n_clusters=2, random_state=0)
        with pytest.raises(ValueError):
            e12.profile_clusters(X, labels, feature_names=["only_one"])


class TestNamingSeeds:
    def test_basic(self):
        X = _make_blobs(n_per_cluster=30)
        labels = e12.run_kmeans(X, n_clusters=3, random_state=0)
        profiles = e12.profile_clusters(X, labels, ["x", "y"])
        seeds = e12.build_naming_seeds(profiles, template_prefix="seg")
        assert len(seeds) == 3
        for s in seeds:
            assert s["suggested_name"].startswith("seg_")
            assert len(s["top_features"]) <= 3
            assert "description_seed" in s

    def test_empty_profiles(self):
        seeds = e12.build_naming_seeds([])
        assert seeds == []


class TestSegmentationTemplate:
    def test_basic(self):
        X = _make_blobs(n_per_cluster=30)
        labels = e12.run_kmeans(X, n_clusters=3, random_state=0)
        profiles = e12.profile_clusters(X, labels, ["x", "y"])
        seeds = e12.build_naming_seeds(profiles)
        tmpl = e12.segmentation_template(
            profiles, seeds, total_samples=len(X),
        )
        assert tmpl["total_samples"] == 90
        assert tmpl["n_segments"] == 3
        assert sum(s["size"] for s in tmpl["segments"]) == 90
        # shares should sum to ~1
        assert math.isclose(
            sum(s["share"] for s in tmpl["segments"]),
            1.0, abs_tol=1e-9,
        )


class TestOrchestrator:
    def test_run_clustering_with_feature_names(self):
        X = _make_blobs(n_per_cluster=20)
        r = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 3, "random_state": 0},
            feature_names=["x", "y"],
            naming_prefix="cluster",
        )
        assert r.algorithm == "kmeans"
        assert r.n_clusters == 3
        for prof in r.profiles:
            assert "x" in prof["features"]
            assert "y" in prof["features"]
        for seed in r.naming_seeds:
            assert seed["suggested_name"].startswith("cluster_")
        assert r.segmentation_template["n_segments"] == 3

    def test_standardize_toggle(self):
        X = _make_blobs(n_per_cluster=20)
        # without standardization: cluster means raw
        r = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 3, "random_state": 0},
            standardize=False,
        )
        # with standardization: cluster means ≈ 0 in standardised space
        r_std = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 3, "random_state": 0},
            standardize=True,
        )
        # both should give 3 clusters but feature distributions differ
        assert r.n_clusters == r_std.n_clusters == 3

    def test_payload_json_safe(self):
        import json
        X = _make_blobs(n_per_cluster=10)
        r = e12.run_clustering(
            X, algorithm="kmeans",
            kmeans_kwargs={"n_clusters": 2, "random_state": 0},
        )
        p = e12.result_payload(r)
        json.dumps(p)  # must not raise


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = e12.E12_CLUSTERING_TOOL_NAMES
        for n in ("e12_run_kmeans", "e12_run_dbscan",
                  "e12_run_hierarchical", "e12_compute_silhouette",
                  "e12_compute_calinski_harabasz",
                  "e12_profile_clusters", "e12_build_naming_seeds",
                  "e12_segmentation_template", "e12_run_clustering",
                  "e12_result_payload"):
            assert n in names
