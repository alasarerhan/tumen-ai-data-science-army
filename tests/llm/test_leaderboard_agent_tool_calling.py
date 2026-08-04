"""leaderboard_agent tool doğrulaması (PM kararı: stub test yok).

Tüm tool'lar ``store: ExperimentStore`` arg alır (Pydantic JSON-serializable
değil, runtime object). Bu tool'lar model-driven harness kapsamı dışındadır;
Faz C API entegrasyon testinde kapsanmalıdır. Burada ``pytest.skip`` ile
belgelenir.
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.leaderboard_agent import (
    EXPERIMENT_TRACKER_TOOLS,
    leaderboard_wrapped,
    parallel_coordinates_payload_wrapped,
    record_run_wrapped,
    summarise_metrics_wrapped,
)
from tests.llm._driver import _drive_tool_call  # noqa: F401  (kullanılmasa da pattern uyumu)

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# STATEFUL: tüm tool'lar ExperimentStore arg alır → API test Faz C kapsamında
# ---------------------------------------------------------------------------


def test_record_run_stateful_skipped():
    sig = inspect.signature(record_run_wrapped.func)
    assert "store" in sig.parameters
    pytest.skip("stateful tool: ExperimentStore arg, Pydantic JSON-serializable değil; "
                "Faz C API entegrasyon testinde kapsanacak")


def test_leaderboard_stateful_skipped():
    sig = inspect.signature(leaderboard_wrapped.func)
    assert "store" in sig.parameters
    pytest.skip("stateful tool: ExperimentStore arg; Faz C API test kapsamında")


def test_summarise_metrics_stateful_skipped():
    sig = inspect.signature(summarise_metrics_wrapped.func)
    assert "store" in sig.parameters
    pytest.skip("stateful tool: ExperimentStore arg; Faz C API test kapsamında")


def test_parallel_coordinates_payload_stateful_skipped():
    sig = inspect.signature(parallel_coordinates_payload_wrapped.func)
    assert "store" in sig.parameters
    pytest.skip("stateful tool: ExperimentStore arg; Faz C API test kapsamında")


# Registry'deki tool sayısını belgele (gelecekte stateful/PURE ayrımı değişirse
# bu test bizi uyarır).
def test_stateful_tool_count():
    assert len(EXPERIMENT_TRACKER_TOOLS) == 4, (
        f"EXPERIMENT_TRACKER_TOOLS sayısı değişti ({len(EXPERIMENT_TRACKER_TOOLS)}); "
        "yeni tool'lar PURE ise model-driven test ekle."
    )
