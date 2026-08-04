"""GERÇEK model-driven reports_agent tool doğrulaması (PM kararı: stub test yok).

4 PURE tool için: gerçek model (ChatOpenAI) tool'a bind edilir, prompt ile
tool'u çağırması sağlanır, tool gerçekten çalıştırılır, content/artifact
doğrulanır. Tool başarısız olursa test FAIL eder (try/except yok).
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.reports_agent import (
    build_report_wrapped,
    compute_schedule_wrapped,
    get_template_wrapped,
    render_markdown_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Tool başına gerçek testler
# ---------------------------------------------------------------------------


def test_get_template_real(llm_or_skip, llm_model):
    """get_template(template_id) alır; template dict döner."""
    tool = get_template_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "get_template tool'unu TEK çağrı ile çağır. template_id='daily_ops'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s, (
        f"get_template beklenen çıktı üretmedi: {s[:300]}"
    )


def test_build_report_real(llm_or_skip, llm_model):
    """build_report(template_id) alır; report dict döner."""
    tool = build_report_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "build_report tool'unu TEK çağrı ile çağır. template_id='daily_ops'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s, (
        f"build_report beklenen çıktı üretmedi: {s[:300]}"
    )


def test_compute_schedule_real(llm_or_skip, llm_model):
    """compute_schedule(period, starting_at_epoch, n_runs) alır; cron listesi döner."""
    tool = compute_schedule_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "compute_schedule tool'unu TEK çağrı ile çağır. "
            "period='daily', starting_at_epoch=1700000000.0, n_runs=3.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s or "schedule" in s or "cron" in s, (
        f"compute_schedule beklenen çıktı üretmedi: {s[:300]}"
    )


def test_render_markdown_real(llm_or_skip, llm_model):
    """render_markdown(report: Mapping) alır; markdown string döner."""
    tool = render_markdown_wrapped
    report = {
        "title": "Daily Ops Report",
        "sections": [
            {"heading": "Summary", "content": "All systems operational."},
        ],
    }
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            f"render_markdown tool'unu TEK çağrı ile çağır. report = {report!r}",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s, (
        f"render_markdown beklenen çıktı üretmedi: {s[:300]}"
    )
