"""leaderboard_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/leaderboard_agent.py — 4 tool.

Strateji:
- TÜM tool'lar ``store: ExperimentStore`` arg alır (Pydantic JSON-serializable
  değil, runtime object). Model-driven harness'te çalışmazlar; tools/leaderboard.py
  doğrudan çağrılır. Gerçek state instance test'te yaratılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.leaderboard_agent import (
    EXPERIMENT_TRACKER_TOOLS,
)
from ai_data_science_team.tools.leaderboard import (
    ExperimentRecord,
    ExperimentStore,
    leaderboard,
    parallel_coordinates_payload,
    record_run,
    summarise_metrics,
)

pytestmark = pytest.mark.llm


def _seeded_store() -> ExperimentStore:
    """Test için taze, izole ExperimentStore — gerçek state instance.

    2 model × 2 metric ile doldurulmuş kayıtlar; leaderboard / summarise /
    parallel_coordinates payload testlerinde tutarlı sonuç üretir.
    """
    store = ExperimentStore()
    store.records.append(
        ExperimentRecord(
            run_id="r1",
            experiment_id="exp1",
            model_id="model_a",
            metrics={"accuracy": 0.91, "f1": 0.88},
            params={"lr": 0.01},
            tags={},
            created_at=1.0,
            is_champion=True,
        )
    )
    store.records.append(
        ExperimentRecord(
            run_id="r2",
            experiment_id="exp1",
            model_id="model_b",
            metrics={"accuracy": 0.93, "f1": 0.85},
            params={"lr": 0.005},
            tags={},
            created_at=2.0,
            is_champion=False,
        )
    )
    return store


# ---------------------------------------------------------------------------
# STATEFUL: tüm tool'lar ExperimentStore arg alır → tools/leaderboard.py
# ---------------------------------------------------------------------------


def test_record_run_real():
    """record_run(store, *, experiment_id, model_id, metrics, ...) → ExperimentRecord.

    Yeni bir store'a bir kayıt eklenir ve store.records uzunluğu artar.
    """
    store = ExperimentStore()
    rec = record_run(
        store=store,
        experiment_id="exp1",
        model_id="model_x",
        metrics={"accuracy": 0.9},
        params={"lr": 0.01},
    )
    assert rec is not None
    assert rec.run_id
    assert rec.experiment_id == "exp1"
    assert rec.model_id == "model_x"
    assert rec.metrics == {"accuracy": 0.9}
    assert len(store.records) == 1


def test_leaderboard_real():
    """leaderboard(store, experiment_id, primary_metric, *, ...) → List[LeaderboardEntry]."""
    store = _seeded_store()
    entries = leaderboard(
        store=store,
        experiment_id="exp1",
        primary_metric="accuracy",
        higher_is_better=True,
    )
    assert isinstance(entries, list)
    assert len(entries) == 2
    # higher_is_better=True → accuracy=0.93 (model_b) 1. sırada
    assert entries[0].model_id == "model_b"
    assert entries[0].primary_metric == "accuracy"
    assert entries[0].rank == 1
    # delta_to_champion: model_b (non-champion) - model_a (champion 0.91) = 0.02
    assert abs(float(entries[0].delta_to_champion) - 0.02) < 1e-9


def test_summarise_metrics_real():
    """summarise_metrics(store, experiment_id, metric) → {n, mean, std, min, max}."""
    store = _seeded_store()
    out = summarise_metrics(
        store=store,
        experiment_id="exp1",
        metric="accuracy",
    )
    assert isinstance(out, dict)
    assert "n" in out and "mean" in out
    assert out["n"] == 2.0
    # mean(0.91, 0.93) = 0.92
    assert abs(float(out["mean"]) - 0.92) < 1e-9
    assert out["min"] == 0.91
    assert out["max"] == 0.93


def test_parallel_coordinates_payload_real():
    """parallel_coordinates_payload(store, experiment_id, metric_columns) → dict."""
    store = _seeded_store()
    out = parallel_coordinates_payload(
        store=store,
        experiment_id="exp1",
        metric_columns=["accuracy", "f1"],
    )
    assert isinstance(out, dict)
    assert out["experiment_id"] == "exp1"
    assert out["metrics"] == ["accuracy", "f1"]
    points = out["points"]
    assert len(points) == 2
    run_ids = {p["run_id"] for p in points}
    assert run_ids == {"r1", "r2"}
    # Her nokta seçilen metricleri içermeli
    for p in points:
        assert "accuracy" in p and "f1" in p


# Registry'deki tool sayısını belgele (gelecekte stateful/PURE ayrımı değişirse
# bu test bizi uyarır).
def test_stateful_tool_count():
    assert len(EXPERIMENT_TRACKER_TOOLS) == 4, (
        f"EXPERIMENT_TRACKER_TOOLS sayısı değişti ({len(EXPERIMENT_TRACKER_TOOLS)}); "
        "yeni tool'lar PURE ise model-driven test ekle."
    )
