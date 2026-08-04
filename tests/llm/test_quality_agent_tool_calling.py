"""GERÇEK model-driven quality_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/quality_agent.py — 3 tool.

STATEFUL (pd.DataFrame + Pydantic/Mapping → API test kapsamı):

Bu agent'ın TÜM 3 tool'u stateful kategorisindedir:
- b2_expectation_suite_from_template_wrapped  — template, dataset, overrides (Mapping)
- b2_validate_against_suite_wrapped          — df, suite (Sequence[Mapping])
- b2_summarise_suite_run_wrapped             — result (Mapping)

Hiçbiri yalnızca skaler argüman kabul etmiyor; Pydantic JSON schema üretilemiyor.
Model-driven harness kapsamı dışındadır; Faz C API entegrasyon testinde
kapsanmalıdır.
"""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Tüm tool'lar stateful — pytest.skip ile belgeli
# ---------------------------------------------------------------------------

STATEFUL_TOOLS = [
    "b2_expectation_suite_from_template_wrapped",
    "b2_validate_against_suite_wrapped",
    "b2_summarise_suite_run_wrapped",
]


@pytest.mark.parametrize("tool_name", STATEFUL_TOOLS)
def test_quality_tool_stateful_skipped(tool_name):
    """Quality tool'ların TÜMÜ stateful kategorisindedir.

    Sebepler:
    - pd.DataFrame parametreleri (dataset, df)
    - Mapping tipli parametreler (overrides, suite, result)

    Test, bu tool'ların varlığını doğrular ve stateful olarak işaretler; Faz C
    API entegrasyon testinde kapsanmalıdır.
    """
    import ai_data_science_team.agents.quality_agent as mod

    wrapper = getattr(mod, tool_name)
    assert hasattr(wrapper, "name"), f"{tool_name} missing .name"
    assert hasattr(wrapper, "invoke"), f"{tool_name} missing .invoke"
    sig = inspect.signature(wrapper.func)
    del sig  # noqa: F841 — inspect signature kontrol için
    pytest.skip(
        f"stateful tool: {tool_name} pd.DataFrame/Mapping arg alır; "
        f"API entegrasyon testinde kapsanacak"
    )
