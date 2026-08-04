"""Paylaşılan model-driven test yardımcıları.

Her agent/tool test dosyası (`tests/llm/test_<name>_tool_calling.py`)
bu yardımcıları kullanır; gerçek LLM çağrısı yaparak tool'un
davranışını doğrular.

Yapı:
- ``_drive_tool_call(model, tool, prompt, injected=None)``
    Model'i tool ile bağlar, prompt'u gönderir, tool_call alır, InjectedState
    parametrelerini enjekte eder ve tool'u çalıştırır.

- ``_assert_result(result, name)``
    Tuple (content, artifact) ya da ToolMessage'ı normalize eder; boş ise
    FAIL eder.

- ``_is_pure(tool) -> bool``
    Tool fonksiyonu gövdesinde InjectedState, KPIHistory, AlarmRule gibi
    stateful imzalara sahipse False döner; bu tool'lar API test kapsamındadır.

Kullanım:
    from tests.llm._driver import _drive_tool_call, _assert_result
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage


def _drive_tool_call(model, tool, prompt: str, injected: dict | None = None):
    """Model tool'u çağırır → tool çalışır.

    ``injected``: InjectedState parametrelerine enjekte edilecek dict (örn.
    ``{"data_raw": df_dict}``). None ise yalnızca model'in sağladığı
    arg'lar kullanılır.
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
    if injected:
        # InjectedState — model şemasında yok, platform state'inden enjekte edilir
        args.setdefault("data_raw", injected)
    return tool.invoke({
        "name": call["name"],
        "args": args,
        "id": call.get("id", "1"),
        "type": "tool_call",
    })


def _assert_result(result, name: str):
    """content_and_artifact → (content, artifact); content-only → str/ToolMessage. Boşsa FAIL.

    LangChain sürüm davranışı değişken: tool.invoke() ya tuple(content, artifact),
    ya da ToolMessage(content=..., artifact=...) döner. İkisini de kabul eder.
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


__all__ = ["_drive_tool_call", "_assert_result"]
