"""Tests for J11 Shadow/Canary tool."""
from __future__ import annotations


import pytest

import ai_data_science_team.tools.j11_shadow_canary as j11


@pytest.fixture
def store():
    return j11.DeploymentStore()


@pytest.fixture
def running_deployment(store):
    d = j11.start_deployment(
        store,
        challenger_model_id="new_model",
        champion_model_id="old_model",
        traffic_split=0.10,
        mode="canary",
        error_rate_max=0.05,
        latency_p99_max_ms=200.0,
        min_samples=50,
    )
    for i in range(60):
        is_error = (i % 10 == 0)
        j11.record_live_sample(
            store, d.deployment_id,
            variant="challenger",
            latency_ms=80.0 + i,
            error=is_error,
            score=0.7 + 0.001 * i,
        )
        j11.record_live_sample(
            store, d.deployment_id,
            variant="champion",
            latency_ms=70.0,
            error=False,
            score=0.65,
        )
    return d


class TestStartDeployment:
    def test_returns_deployment(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="new", champion_model_id="old",
            traffic_split=0.05, mode="shadow",
        )
        assert d.challenger_model_id == "new"
        assert d.mode == "shadow"
        assert d.status == "running"
        assert d.traffic_split == 0.05

    def test_invalid_mode(self, store):
        with pytest.raises(ValueError):
            j11.start_deployment(
                store, challenger_model_id="x", champion_model_id="y",
                traffic_split=0.5, mode="blue_green",
            )

    def test_invalid_traffic_split(self, store):
        with pytest.raises(ValueError):
            j11.start_deployment(
                store, challenger_model_id="x", champion_model_id="y",
                traffic_split=1.5,
            )


class TestRecordSample:
    def test_appends_sample(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        j11.record_live_sample(
            store, d.deployment_id, variant="challenger",
            latency_ms=50.0, error=False,
        )
        assert len(d.samples) == 1

    def test_invalid_variant(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        with pytest.raises(ValueError):
            j11.record_live_sample(
                store, d.deployment_id, variant="treatment",
                latency_ms=50.0, error=False,
            )

    def test_unknown_deployment(self, store):
        with pytest.raises(KeyError):
            j11.record_live_sample(
                store, "nope", variant="challenger",
                latency_ms=50.0, error=False,
            )


class TestEvaluateRollback:
    def test_insufficient_data(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5, min_samples=100,
        )
        for _ in range(10):
            j11.record_live_sample(
                store, d.deployment_id, variant="challenger",
                latency_ms=80.0, error=False,
            )
        v = j11.evaluate_rollback(store, d.deployment_id)
        assert v["verdict"] == "insufficient_data"

    def test_ok_when_within_policy(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
            error_rate_max=0.5, latency_p99_max_ms=10000.0, min_samples=10,
        )
        for i in range(20):
            j11.record_live_sample(
                store, d.deployment_id, variant="challenger",
                latency_ms=100.0 + i, error=False,
            )
        v = j11.evaluate_rollback(store, d.deployment_id)
        assert v["verdict"] == "ok"
        assert v["reasons"] == []

    def test_rollback_on_high_error_rate(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5, error_rate_max=0.05, min_samples=20,
        )
        for _ in range(30):
            j11.record_live_sample(
                store, d.deployment_id, variant="challenger",
                latency_ms=80.0, error=True,
            )
        v = j11.evaluate_rollback(store, d.deployment_id)
        assert v["verdict"] == "rollback"
        assert any("error_rate" in r for r in v["reasons"])

    def test_rollback_on_high_latency(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5, latency_p99_max_ms=100.0, min_samples=20,
        )
        for i in range(30):
            j11.record_live_sample(
                store, d.deployment_id, variant="challenger",
                latency_ms=200.0 + i, error=False,
            )
        v = j11.evaluate_rollback(store, d.deployment_id)
        assert v["verdict"] == "rollback"
        assert any("latency" in r for r in v["reasons"])


class TestSummariseDeployment:
    def test_summarise_shape(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        for v in ("champion", "challenger"):
            for i in range(10):
                j11.record_live_sample(
                    store, d.deployment_id, variant=v,
                    latency_ms=100.0 + i, error=False, score=0.7,
                )
        summary = j11.summarise_deployment(store, d.deployment_id)
        assert summary["deployment_id"] == d.deployment_id
        assert "champion" in summary["by_variant"]
        assert "challenger" in summary["by_variant"]
        assert summary["by_variant"]["champion"]["n"] == 10.0
        assert summary["by_variant"]["challenger"]["n"] == 10.0

    def test_summarise_unknown(self, store):
        with pytest.raises(KeyError):
            j11.summarise_deployment(store, "nope")


class TestMarkStatus:
    def test_mark_promoted(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        j11.mark_status(store, d.deployment_id, "promoted")
        assert d.status == "promoted"

    def test_invalid_status(self, store):
        d = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        with pytest.raises(ValueError):
            j11.mark_status(store, d.deployment_id, "aborted")


class TestListDeployments:
    def test_filter_by_status(self, store):
        d1 = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        d2 = j11.start_deployment(
            store, challenger_model_id="x", champion_model_id="y",
            traffic_split=0.5,
        )
        j11.mark_status(store, d2.deployment_id, "rolled_back")
        running = j11.list_deployments(store, status="running")
        rolled = j11.list_deployments(store, status="rolled_back")
        assert d1 in running and d2 not in running
        assert d2 in rolled and d1 not in rolled

