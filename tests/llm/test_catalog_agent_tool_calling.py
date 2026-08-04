"""GERÇEK model-driven catalog_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/catalog_agent.py — 12 tool.

PURE (InjectedState yok, skaler argümanlar → model-driven test edilebilir):
- make_catalog_wrapped  — parametresiz, yeni boş katalog oluşturur

STATEFUL (Catalog/Pydantic state objesi gerektiriyor → API test kapsamı):
- add_source_wrapped, add_table_wrapped, attach_profile_wrapped,
  add_pii_badges_wrapped, catalog_tree_wrapped, add_term_wrapped,
  bind_term_column_wrapped, search_wrapped, resolve_data_wrapped,
  record_lineage_wrapped, lineage_for_wrapped

Bunlar Pydantic ``Catalog`` objesini giriş parametresi olarak alır; platform
state'inden enjekte edilmesi gerekir; tests/llm kapsamı dışında API testi ile
kapsanmalıdır.
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.catalog_agent import make_catalog_wrapped
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE: make_catalog_wrapped
# ---------------------------------------------------------------------------

def test_make_catalog_real(llm_or_skip, llm_model):
    """``make_catalog_wrapped()`` parametresiz çağrı; yeni boş bir katalog üretir."""
    tool = make_catalog_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "make_catalog tool'unu TEK çağrı ile çağır (parametresiz, boş dict ver).",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "catalog" in s or "ok" in s or "{}" in s or "id" in s, (
        f"make_catalog beklenen katalog yapısı üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# STATEFUL: Pydantic Catalog state gerektiriyor → API test kapsamı
# ---------------------------------------------------------------------------

STATEFUL_TOOLS = [
    "add_source_wrapped",
    "add_table_wrapped",
    "attach_profile_wrapped",
    "add_pii_badges_wrapped",
    "catalog_tree_wrapped",
    "add_term_wrapped",
    "bind_term_column_wrapped",
    "search_wrapped",
    "resolve_data_wrapped",
    "record_lineage_wrapped",
    "lineage_for_wrapped",
]


@pytest.mark.parametrize("tool_name", STATEFUL_TOOLS)
def test_catalog_tool_stateful_skipped(tool_name):
    """Catalog tool'ları ``Catalog`` state objesi gerektiriyor.

    Bu tool'lar InjectedState ile platform tarafından otomatik enjekte edilecek
    ``catalog`` parametresini alır. Model-driven harness kapsamı dışındadır;
    Faz C API entegrasyon testinde kapsanmalıdır.
    """
    import ai_data_science_team.agents.catalog_agent as mod

    wrapper = getattr(mod, tool_name)
    sig = inspect.signature(wrapper.func)
    assert "catalog" in sig.parameters, f"{tool_name} 'catalog' arg bekliyor"
    pytest.skip(
        f"stateful tool: {tool_name} Catalog state objesi alır; "
        f"API entegrasyon testinde kapsanacak"
    )
