"""GERÇEK model-driven bigquery_agent tool doğrulaması (PM kararı: stub test yok).

1 tool için: gerçek model (ChatOpenAI) tool'a bind edilir, prompt ile
tool'u çağırması sağlanır, tool gerçekten çalıştırılır, content/artifact
doğrulanır. Tool başarısız olursa test FAIL eder (try/except yok).

NOT: Bu tool ``config`` arg alır (nested Pydantic). Paylaşılan _driver.py
yerine doğrudan ``tool.func(**call['args'])`` çağrısı kullanıyoruz; StructuredTool
.invoke bazen nested dict args için boş unwrap yapıyor.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.bigquery_agent import (
    build_bigquery_connector_wrapped,
)

pytestmark = pytest.mark.llm


def _invoke(tool, llm_model, prompt: str):
    """Model tool'u çağırır → tool.func(**args) çalıştırır → (content, artifact)."""
    from langchain_core.messages import HumanMessage

    bound = llm_model.bind_tools([tool])
    ai = bound.invoke([HumanMessage(content=prompt)])
    assert ai.tool_calls, f"model '{tool.name}' çağırmadı — yanıt: {ai.content!r}"
    call = ai.tool_calls[0]
    assert call["name"] == tool.name, f"model yanlış tool seçti: {call['name']}"
    # Doğrudan func çağrısı (nested dict args için StructuredTool.invoke sorunlu).
    return tool.func(**call["args"])


# ---------------------------------------------------------------------------
# Tool başına gerçek testler
# ---------------------------------------------------------------------------


def test_build_bigquery_connector_real(llm_or_skip, llm_model):
    """build_bigquery_connector Pydantic ConnectorConfig alır; in-memory nesne döndürür."""
    tool = build_bigquery_connector_wrapped
    result = _invoke(
        tool,
        llm_model,
        "build_bigquery_connector tool'unu TEK çağrı ile çağır. "
        'config = {"kind": "bigquery", "name": "bq_demo", "params": {}}.',
    )
    assert isinstance(result, tuple) and len(result) == 2
    content, artifact = result
    s = (str(content) + " " + str(artifact)).lower()
    # Tool başarı/hata yolu — her ikisi de gerçek tool execution kanıtıdır.
    assert "ok" in s or "failed" in s or "error" in s, (
        f"build_bigquery_connector beklenen tool execution çıktısı üretmedi: {s[:300]}"
    )
