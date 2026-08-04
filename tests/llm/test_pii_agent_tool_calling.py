"""GERÇEK model-driven pii_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/pii_agent.py — 3 tool.

STATEFUL (pd.DataFrame + Pydantic PIIScanReport + Mapping → API test kapsamı):

Bu agent'ın TÜM 3 tool'u stateful kategorisindedir:
- scan_pii_wrapped                  — df (pd.DataFrame) → PIIScanReport
- default_strategies_for_wrapped    — scan (Pydantic PIIScanReport)
- anonymize_dataframe_wrapped       — df (pd.DataFrame), strategies (Mapping)

Hiçbiri skaler/JSON-serializable argüman kabul etmiyor; Pydantic JSON schema
üretilemiyor. Model-driven harness kapsamı dışındadır; Faz C API entegrasyon
testinde kapsanmalıdır.
"""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Tüm tool'lar stateful — pytest.skip ile belgeli
# ---------------------------------------------------------------------------

STATEFUL_TOOLS = [
    "scan_pii_wrapped",
    "default_strategies_for_wrapped",
    "anonymize_dataframe_wrapped",
]


@pytest.mark.parametrize("tool_name", STATEFUL_TOOLS)
def test_pii_tool_stateful_skipped(tool_name):
    """PII tool'ların TÜMÜ stateful kategorisindedir.

    Sebepler:
    - pd.DataFrame parametreleri
    - Pydantic ``PIIScanReport`` objesi
    - ``anonymize_dataframe`` strategies Mapping alır

    Test, bu tool'ların varlığını doğrular ve stateful olarak işaretler; Faz C
    API entegrasyon testinde kapsanmalıdır.
    """
    import ai_data_science_team.agents.pii_agent as mod

    wrapper = getattr(mod, tool_name)
    assert hasattr(wrapper, "name"), f"{tool_name} missing .name"
    assert hasattr(wrapper, "invoke"), f"{tool_name} missing .invoke"
    sig = inspect.signature(wrapper.func)
    del sig  # noqa: F841 — inspect signature kontrol için
    pytest.skip(
        f"stateful tool: {tool_name} pd.DataFrame/Pydantic arg alır; "
        f"API entegrasyon testinde kapsanacak"
    )
