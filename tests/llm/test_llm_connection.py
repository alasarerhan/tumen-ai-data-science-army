"""GERÇEK LLM bağlantı testi — konfigürasyon doğrulaması.

OPENAI_API_KEY + OPENAI_MODEL .env'de doğru ayarlandığında bu test gerçek
model çağrısı yapar. Mock yok, stub yok. Bağlantı/model hatası test FAIL
eder (gerçek hata yüzeye çıkar).
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

pytestmark = __import__("pytest").mark.llm


def test_llm_connection_real(llm_or_skip, llm_model):
    """Gerçek model çağrısı: non-empty yanıt + model adı doğrulaması."""
    resp = llm_model.invoke([HumanMessage(content="Merhaba, tek kelimeyle yanıtla: hazır")])
    assert resp.content, "model boş yanıt döndü"
    assert isinstance(resp.content, str) and resp.content.strip(), "yanıt string olmalı"
    assert resp.response_metadata.get("model_name"), "yanıt model metadata içermeli"


def test_llm_model_configured(llm_or_skip, llm_model):
    """OPENAI_MODEL gerçekten kullanılıyor (env'den alınıyor)."""
    import os

    model = llm_model.model_name
    env_model = os.environ.get("OPENAI_MODEL", "").strip()
    assert model == env_model, f"model uyumsuz: env={env_model!r} model={model!r}"
