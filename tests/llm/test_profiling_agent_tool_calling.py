"""GERÇEK model-driven profiling_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/profiling_agent.py — 2 tool.

STATEFUL (pd.Series/pd.DataFrame → API test kapsamı):

Bu agent'ın TÜM 2 tool'u stateful kategorisindedir:
- profile_column_wrapped      — series (pd.Series) arg
- profile_dataframe_wrapped   — df (pd.DataFrame) arg

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
    "profile_column_wrapped",
    "profile_dataframe_wrapped",
]


@pytest.mark.parametrize("tool_name", STATEFUL_TOOLS)
def test_profiling_tool_stateful_skipped(tool_name):
    """Profiling tool'ların TÜMÜ stateful kategorisindedir.

    Sebepler:
    - pd.Series / pd.DataFrame parametreleri
    - İçeride Pydantic model üretiyorlar (PII signal vb.)

    Test, bu tool'ların varlığını doğrular ve stateful olarak işaretler; Faz C
    API entegrasyon testinde kapsanmalıdır.
    """
    import ai_data_science_team.agents.profiling_agent as mod

    wrapper = getattr(mod, tool_name)
    assert hasattr(wrapper, "name"), f"{tool_name} missing .name"
    assert hasattr(wrapper, "invoke"), f"{tool_name} missing .invoke"
    sig = inspect.signature(wrapper.func)
    del sig  # noqa: F841 — inspect signature kontrol için
    pytest.skip(
        f"stateful tool: {tool_name} pd.Series/pd.DataFrame arg alır; "
        f"API entegrasyon testinde kapsanacak"
    )
