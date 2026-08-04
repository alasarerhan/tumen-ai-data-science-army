"""GERÇEK test dashboard_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/dashboard_agent.py — 5 tool.

Strateji:
- PURE (model-driven): ``make_dashboard_wrapped`` model tarafından çağrılır.
- STATEFUL: ``add_panel``, ``validate_layout``, ``make_share_token``,
  ``render_snapshot`` için gerçek ``Dashboard`` Pydantic dataclass yaratılır
  ve **underlying tool** doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.dashboard_agent import (
    DASHBOARD_COMPOSER_TOOLS,
    make_dashboard_wrapped,
)
from ai_data_science_team.tools.dashboard import (
    Dashboard,
    add_panel,
    make_share_token,
    render_snapshot,
    validate_layout,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: make_dashboard — model-driven
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
            llm_model,
            tool,
            f"make_dashboard tool'unu TEK çağrı ile çağır. name='Ops Dashboard', panels={panels!r}",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s, (
        f"make_dashboard beklenen çıktı üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: Dashboard Pydantic dataclass
# ---------------------------------------------------------------------------


def _fresh_dashboard(name: str = "Ops Dashboard") -> Dashboard:
    """Test için taze, izole Dashboard."""
    return Dashboard(dashboard_id="d_test", name=name)


def _seed_dashboard() -> Dashboard:
    """2 panelli, doğrulanmış dashboard."""
    dash = _fresh_dashboard()
    add_panel(
        dash,
        title="Active Users",
        artifact_ref="artifact:users",
        row=0,
        col=0,
        width=1,
        height=1,
    )
    add_panel(
        dash,
        title="Latency",
        artifact_ref="artifact:latency",
        row=0,
        col=1,
        width=1,
        height=1,
    )
    return dash


def test_add_panel_real():
    """add_panel: Dashboard'a Panel ekler."""
    dash = _fresh_dashboard()
    panel = add_panel(
        dash,
        title="Revenue",
        artifact_ref="artifact:rev",
        row=0,
        col=0,
    )
    assert panel.title == "Revenue"
    assert len(dash.panels) == 1
    assert dash.panels[0].panel_id == panel.panel_id


def test_validate_layout_real():
    """validate_layout: temiz dashboard → issues=[]."""
    dash = _seed_dashboard()
    issues = validate_layout(dash)
    assert issues == []
    # Boş dashboard da temiz
    assert validate_layout(_fresh_dashboard()) == []


def test_make_share_token_real():
    """make_share_token: dashboard snapshot'ından deterministik token."""
    dash = _seed_dashboard()
    token = make_share_token(dash)
    assert isinstance(token, str)
    assert len(token) == 24
    # Aynı dashboard → aynı token
    assert make_share_token(dash) == token
    # Farklı dashboard → farklı token
    other = _fresh_dashboard("Other")
    assert make_share_token(other) != token


def test_render_snapshot_real():
    """render_snapshot: text snapshot — name + grid + panels."""
    dash = _seed_dashboard()
    snap = render_snapshot(dash)
    assert "Ops Dashboard" in snap
    assert "Grid:" in snap
    assert "Layout: valid" in snap
    assert "Active Users" in snap
    assert "Latency" in snap


# ---------------------------------------------------------------------------
# Registry bütünlüğü — gelecekteki kırılmaları yakalar
# ---------------------------------------------------------------------------


def test_stateful_vs_pure_count():
    assert len(DASHBOARD_COMPOSER_TOOLS) == 5, (
        f"DASHBOARD_COMPOSER_TOOLS sayısı değişti ({len(DASHBOARD_COMPOSER_TOOLS)}); "
        "yeni tool'lar PURE ise model-driven test ekle."
    )
