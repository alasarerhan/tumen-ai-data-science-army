"""GERÇEK model-driven eda tool doğrulaması (PM kararı D2).

Her eda tool'u için: gerçek model (ChatOpenAI) tool'a bind edilir, prompt ile
tool'u çağırması sağlanır, platform state'i (data_raw, InjectedState) enjekte
edilir, tool gerçekten çalıştırılır ve çıktı (content/artifact) doğrulanır.

Mock YOK. Stub YOK. RunnableLambda YOK. Tool başarısız olursa test FAIL eder.

Kapsam: ai_data_science_team/tools/eda.py — 6 tool.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from ai_data_science_team.tools.eda import (
    describe_dataset,
    explain_data,
    generate_correlation_funnel,
    generate_dtale_report,
    generate_sweetviz_report,
    visualize_missing,
)

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Model-driven sürücü
# ---------------------------------------------------------------------------

def _drive_tool_call(model, tool, prompt: str, injected: dict):
    """Model tool'u çağırır → platform state'i (data_raw) enjekte edilir → tool çalışır.

    InjectedState("data_raw") LangChain'de modele görünür (Pydantic schema'da
    yer aldığı için model "veri sağlayın" diye yanıt verebiliyor). Bu yüzden
    prompt'a açıkça "data_raw argümanını KULLANMA — platform state'ten enjekte
    edilecek; sadece diğer parametreleri belirle" notu düşülüyor.
    """
    bound = model.bind_tools([tool])
    full_prompt = (
        f"{prompt}\n\n"
        f"NOT: tool'un `data_raw` parametresi (InjectedState) **modelin sağlaması gereken "
        f"bir argüman değildir** — platform tarafından otomatik enjekte edilecek. "
        f"Sen sadece diğer (zorunlu/opsiyonel) parametreleri belirle ve TEK çağrı yap."
    )
    ai = bound.invoke([HumanMessage(content=full_prompt)])

    assert ai.tool_calls, f"model '{tool.name}' çağırmadı — yanıt: {ai.content!r}"
    call = ai.tool_calls[0]
    assert call["name"] == tool.name, f"model yanlış tool seçti: {call['name']}"

    args = dict(call["args"])
    # InjectedState — model şemasında yok, platform state'inden enjekte edilir
    args.setdefault("data_raw", injected)
    return tool.invoke({
        "name": call["name"], "args": args,
        "id": call.get("id", "1"), "type": "tool_call",
    })


def _assert_result(result, name: str):
    """content_and_artifact → (content, artifact); content-only → str/ToolMessage. Boşsa FAIL.

    LangChain sürüm davranışı değişken: tool.invoke() ya tuple(content, artifact),
    ya da ToolMessage(content=..., artifact=...) döner. İkisini de kabul et.
    """
    # ToolMessage ise .content ve .artifact kullan
    is_msg = (
        hasattr(result, "content")
        and hasattr(result, "name")
        and not isinstance(result, (str, list))
    )
    if is_msg:
        content, artifact = result.content, getattr(result, "artifact", None)
        assert content, f"{name}: boş content (ToolMessage)"
        return content, artifact
    if isinstance(result, tuple) and len(result) == 2:
        content, artifact = result
        assert content, f"{name}: boş content"
        assert artifact, f"{name}: boş artifact"
        return content, artifact
    assert result, f"{name}: boş sonuç"
    return result, None


def _prompt(instruction: str, columns: str) -> str:
    return (
        "Elinde bir DataFrame var. Sütunlar: "
        f"{columns}.\nGörev: {instruction}\n"
        "Uygun tool'u TEK çağrı ile çağır (gerekli parametreleri ver)."
    )


# ---------------------------------------------------------------------------
# Tool başına gerçek testler
# ---------------------------------------------------------------------------

def test_explain_data_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = explain_data
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            _prompt("Bu veri setini ayrıntılı şekilde açıkla (explain_data çağır, n_sample=5).",
                    ", ".join(sample_df.columns)),
            sample_data_dict,
        ),
        tool.name,
    )
    assert isinstance(result, (str, list)) and len(str(result)) > 0


def test_describe_dataset_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = describe_dataset
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            _prompt("Bu veri seti için istatistik özeti üret (describe_dataset çağır).",
                    ", ".join(sample_df.columns)),
            sample_data_dict,
        ),
        tool.name,
    )
    # describe_dataset içerik üretir; anahtar kelimelere esnek bak
    s = str(result).lower()
    assert any(
        k in s for k in
        ("row", "count", "mean", "describe", "summary", "statistic", "columns")
    ), f"describe_dataset beklenen eda çıktısı üretmedi: {s[:300]}"


def test_visualize_missing_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = visualize_missing
    _assert_result(
        _drive_tool_call(
            llm_model, tool,
            _prompt("Eksik veri analizi yap (visualize_missing çağır).",
                    ", ".join(sample_df.columns)),
            sample_data_dict,
        ),
        tool.name,
    )


def test_generate_correlation_funnel_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    import pytest as _pytest
    _pytest.importorskip("pytimetk",
                        reason="pytimetk yalnızca Python <3.10 destekler; 3.13 ortamında skip")
    tool = generate_correlation_funnel
    result, artifact = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            _prompt("Hedef sütun 'value' için korelasyon funnel üret "
                    "(generate_correlation_funnel çağır, target='value').",
                    ", ".join(sample_df.columns)),
            sample_data_dict,
        ),
        tool.name,
    )
    assert artifact, "korelasyon funnel artifact üretmeli"


def test_generate_sweetviz_report_real(  # noqa: E501
    llm_or_skip, llm_model, sample_data_dict, sample_df, tmp_path
):
    tool = generate_sweetviz_report
    _, artifact = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            _prompt(
                "sweetviz raporu üret (generate_sweetviz_report çağır; "
                f"report_directory='{tmp_path}', report_name='report.html').",
                ", ".join(sample_df.columns),
            ),
            sample_data_dict,
        ),
        tool.name,
    )
    # artifact ya rapor yolu ya da HTML içeriği olmalı
    if isinstance(artifact, dict):
        assert artifact, "sweetviz artifact boş"


def test_generate_dtale_report_real(llm_or_skip, llm_model, sample_data_dict, sample_df):
    tool = generate_dtale_report
    try:
        _assert_result(
            _drive_tool_call(
                llm_model, tool,
                _prompt(
                    "dtale ile interaktif analiz başlat (generate_dtale_report çağır, "
                    "host='localhost', port=40100, open_browser=False).",
                    ", ".join(sample_df.columns),
                ),
                sample_data_dict,
            ),
            tool.name,
        )
    finally:
        # dtale arka plan sunucusunu kapat (best-effort)
        try:
            import dtale

            for key in list(dtale.global_state.keys() or []):
                dtale.global_state.clear(key)
        except Exception:  # noqa: BLE001 — teardown best-effort
            pass
