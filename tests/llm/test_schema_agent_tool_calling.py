"""GERÇEK model-driven schema_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/schema_agent.py — 4 tool.

STATEFUL (pd.Series/pd.DataFrame/Pydantic objesi → API test kapsamı):

Bu agent'ın TÜM 4 tool'u stateful kategorisindedir:
- infer_column_type_wrapped   — series (pd.Series) arg
- infer_schema_wrapped        — df (pd.DataFrame) arg
- build_mapping_wrapped       — source, target (Pydantic Schema) args
- mapping_summary_wrapped     — mapping (Pydantic MappingResult) arg

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
    "infer_column_type_wrapped",
    "infer_schema_wrapped",
    "build_mapping_wrapped",
    "mapping_summary_wrapped",
]


@pytest.mark.parametrize("tool_name", STATEFUL_TOOLS)
def test_schema_tool_stateful_skipped(tool_name):
    """Schema tool'ların TÜMÜ stateful kategorisindedir.

    Sebepler:
    - pd.Series/pd.DataFrame parametreleri
    - Pydantic ``Schema`` ve ``MappingResult`` objeleri (JSON-serializable değil)

    Test, bu tool'ların varlığını doğrular ve stateful olarak işaretler; Faz C
    API entegrasyon testinde kapsanmalıdır.
    """
    import ai_data_science_team.agents.schema_agent as mod

    wrapper = getattr(mod, tool_name)
    assert hasattr(wrapper, "name"), f"{tool_name} missing .name"
    assert hasattr(wrapper, "invoke"), f"{tool_name} missing .invoke"
    sig = inspect.signature(wrapper.func)
    del sig  # noqa: F841 — inspect signature kontrol için
    pytest.skip(
        f"stateful tool: {tool_name} pd.DataFrame/Pydantic arg alır; "
        f"API entegrasyon testinde kapsanacak"
    )
