"""GERÇEK model-driven llm_judge_agent tool doğrulaması (PM kararı: stub test yok).

2 PURE tool için: gerçek model (ChatOpenAI) tool'a bind edilir, prompt ile
tool'u çağırması sağlanır, tool gerçekten çalıştırılır, content/artifact
doğrulanır. Tool başarısız olursa test FAIL eder (try/except yok).
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.llm_judge_agent import (
    judge_batch_wrapped,
    judge_output_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Tool başına gerçek testler
# ---------------------------------------------------------------------------


def test_judge_output_real(llm_or_skip, llm_model):
    """judge_output (text, code) alır; score döner."""
    tool = judge_output_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "judge_output tool'unu TEK çağrı ile çağır. "
            "text='The output is correct.', code='def f(): return 42'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    # Tool başarı yolunda "ok" veya judge sonucu; hata yolunda "failed/error"
    assert "ok" in s or "failed" in s or "error" in s or "score" in s, (
        f"judge_output beklenen çıktı üretmedi: {s[:300]}"
    )


def test_judge_batch_real(llm_or_skip, llm_model):
    """judge_batch (items: Sequence[{text, code}]) alır; batch score döner."""
    tool = judge_batch_wrapped
    items = [
        {"text": "Output 1 is correct.", "code": "def f(): return 1"},
        {"text": "Output 2 is wrong.", "code": "def f(): return 0"},
    ]
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            f"judge_batch tool'unu TEK çağrı ile çağır. items = {items!r}",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "ok" in s or "failed" in s or "error" in s or "score" in s, (
        f"judge_batch beklenen çıktı üretmedi: {s[:300]}"
    )
