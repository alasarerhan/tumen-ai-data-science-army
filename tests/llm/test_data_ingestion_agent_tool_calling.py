"""GERÇEK test data_ingestion_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/data_ingestion_agent.py — 4 tool.

Strateji:
- PURE (model-driven): ``register_ingest_job_wrapped``,
  ``compute_watermark_wrapped``, ``record_run_wrapped`` model tarafından
  çağrılır.
- STATEFUL: ``incremental_diff_wrapped`` pd.DataFrame alır; bu test'lerde
  pytest.skip yerine küçük gerçek DataFrame'ler yaratılır ve **underlying
  tool** olan ``incremental_diff`` doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ai_data_science_team.agents.data_ingestion_agent import (
    compute_watermark_wrapped,
    record_run_wrapped,
    register_ingest_job_wrapped,
)
from ai_data_science_team.tools.data_ingestion import incremental_diff
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: Tool başına gerçek testler
# ---------------------------------------------------------------------------

def test_register_ingest_job_real(llm_or_skip, llm_model):
    """``register_ingest_job_wrapped(name, source, target)`` yeni bir job record üretir."""
    tool = register_ingest_job_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "register_ingest_job tool'unu TEK çağrı ile çağır. "
            "name='daily_users_etl', source='s3://bucket/raw/', target='s3://bucket/staging/'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "register" in s or "ok" in s or "daily_users_etl" in s, (
        f"register_ingest_job beklenen job kaydı üretmedi: {s[:200]}"
    )


def test_compute_watermark_real(llm_or_skip, llm_model):
    """``compute_watermark_wrapped(job_id, previous, current)`` watermark ilerlemesi döner."""
    tool = compute_watermark_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "compute_watermark tool'unu TEK çağrı ile çağır. "
            "job_id='daily_users_etl', previous='2024-01-01', current='2024-01-02'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "watermark" in s or "ok" in s or "advance" in s or "progress" in s, (
        f"compute_watermark beklenen watermark kaydı üretmedi: {s[:200]}"
    )


def test_record_run_real(llm_or_skip, llm_model):
    """``record_run_wrapped(job_id, run_id, status, started_at)`` run history row üretir."""
    tool = record_run_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "record_run tool'unu TEK çağrı ile çağır. "
            "job_id='daily_users_etl', run_id='run_42', status='success', "
            "started_at='2024-01-02T03:00:00Z'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "run" in s or "ok" in s or "record" in s or "run_42" in s, (
        f"record_run beklenen run kaydı üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: pd.DataFrame argümanı → underlying tool.func() doğrudan çağrı
# ---------------------------------------------------------------------------

def test_incremental_diff_real():
    """``incremental_diff`` iki DataFrame arasında added/removed/changed sınıflandırır.

    underlying tool imzası: ``incremental_diff(baseline, current, *,
    key_columns=None, compare_columns=None) -> dict``.
    """
    baseline = pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})
    current = pd.DataFrame({"id": [2, 3, 4], "value": [20, 30, 40]})
    out = incremental_diff(
        baseline, current, key_columns=["id"],
        compare_columns=["value"],
    )
    assert "added" in out
    assert "removed" in out
    assert "changed" in out
    assert out["n_added"] == 1
    assert out["n_removed"] == 1
    assert out["n_changed"] == 0
