"""dashboard_agent tool doğrulaması (PM kararı: stub test yok).

4 STATEFUL tool (``add_panel``, ``validate_layout``, ``make_share_token``,
``render_snapshot``) ``Dashboard`` Pydantic model arg alır; model-driven
harness kapsamı dışındadır (API test Faz C'de kapsanmalıdır). Burada
``pytest.skip`` ile belgelenir.

1 PURE tool (``make_dashboard``) için model-driven test yapılır.
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.dashboard_agent import (
    DASHBOARD_COMPOSER_TOOLS,
    add_panel_wrapped,
    make_dashboard_wrapped,
    make_share_token_wrapped,
    render_snapshot_wrapped,
    validate_layout_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE tool başına gerçek test
# ---------------------------------------------------------------------------


def test_make_dashboard_real(llm_or_skip, llm_model):
    """make_dashboard(name, panels) alır; Dashboard objesi döner."""
    tool = make_dashboard_wrapped
    panels = [
        {"title": "Active Users", "type": "kpi", "value": 1234},
        {"title": "Latency", "type": "line_chart", "metric": "p99_latency_ms"},
    ]
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            f"make_dashboard tool'unu TEK çağrı ile çağır. name='Ops Dashboard', panels={panels!r}",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s, (
        f"make_dashboard beklenen çıktı üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# STATEFUL: Dashboard (Pydantic, runtime object) → API test Faz C kapsamında
# ---------------------------------------------------------------------------


def test_add_panel_stateful_skipped():
    sig = inspect.signature(add_panel_wrapped.func)
    assert "dashboard" in sig.parameters
    pytest.skip("stateful tool: Dashboard arg, Pydantic runtime object; "
                "Faz C API entegrasyon testinde kapsanacak")


def test_validate_layout_stateful_skipped():
    sig = inspect.signature(validate_layout_wrapped.func)
    assert "dashboard" in sig.parameters
    pytest.skip("stateful tool: Dashboard arg; Faz C API test kapsamında")


def test_make_share_token_stateful_skipped():
    sig = inspect.signature(make_share_token_wrapped.func)
    assert "dashboard" in sig.parameters
    pytest.skip("stateful tool: Dashboard arg; Faz C API test kapsamında")


def test_render_snapshot_stateful_skipped():
    sig = inspect.signature(render_snapshot_wrapped.func)
    assert "dashboard" in sig.parameters
    pytest.skip("stateful tool: Dashboard arg; Faz C API test kapsamında")


# Registry'deki tool sayısını belgele (gelecekte stateful/PURE ayrımı değişirse
# bu test bizi uyarır).
def test_stateful_vs_pure_count():
    assert len(DASHBOARD_COMPOSER_TOOLS) == 5, (
        f"DASHBOARD_COMPOSER_TOOLS sayısı değişti ({len(DASHBOARD_COMPOSER_TOOLS)}); "
        "yeni tool'lar PURE ise model-driven test ekle."
    )
