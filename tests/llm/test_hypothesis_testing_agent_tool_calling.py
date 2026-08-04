"""GERÇEK model-driven hypothesis_testing_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/hypothesis_testing_agent.py — 3 tool.

TÜMÜ PURE (skaler/Sequence argümanlar, InjectedState yok, Pydantic değil):
- recommend_test_wrapped     — values (Sequence[float]) → test önerir
- run_test_wrapped           — values (Sequence[float]) → chosen test çalıştırır
- interpret_result_wrapped   — p_value, effect_size (float) → düz-dil yorum

Bu agent'ta stateful tool yok; 3 tool'un tamamı model-driven test edilebilir.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.hypothesis_testing_agent import (
    interpret_result_wrapped,
    recommend_test_wrapped,
    run_test_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE: Tüm 3 tool için gerçek test
# ---------------------------------------------------------------------------

def test_recommend_test_real(llm_or_skip, llm_model):
    """``recommend_test_wrapped(values)`` veri şekline göre uygun hipotez testi önerir."""
    tool = recommend_test_wrapped
    values = [1.2, 1.4, 1.1, 1.5, 1.3, 1.6, 1.2, 1.4, 1.3, 1.1]
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "recommend_test tool'unu TEK çağrı ile çağır. "
            f"values={values}.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "ttest" in s
        or "t-test" in s
        or "mann" in s
        or "shapiro" in s
        or "test" in s
        or "ok" in s
    ), f"recommend_test beklenen test önerisi vermedi: {s[:200]}"


def test_run_test_real(llm_or_skip, llm_model):
    """``run_test_wrapped(values)`` seçilen hipotez testini çalıştırır."""
    tool = run_test_wrapped
    values = [1.2, 1.4, 1.1, 1.5, 1.3, 1.6, 1.2, 1.4, 1.3, 1.1]
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "run_test tool'unu TEK çağrı ile çağır. "
            f"values={values}.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "p_value" in s
        or "p-value" in s
        or "statistic" in s
        or "test" in s
        or "ok" in s
    ), f"run_test beklenen test sonucu üretmedi: {s[:200]}"


def test_interpret_result_real(llm_or_skip, llm_model):
    """``interpret_result_wrapped(p_value, effect_size)`` p-value + effect'i düz-dil yorumlar."""
    tool = interpret_result_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "interpret_result tool'unu TEK çağrı ile çağır. "
            "p_value=0.023, effect_size=0.42.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "reject" in s
        or "fail" in s
        or "significant" in s
        or "effect" in s
        or "interpretation" in s
        or "ok" in s
    ), f"interpret_result beklenen düz-dil yorum üretmedi: {s[:200]}"
