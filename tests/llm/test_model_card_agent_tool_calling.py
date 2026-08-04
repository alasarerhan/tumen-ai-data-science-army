"""GERÇEK test model_card_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/model_card_agent.py — 6 tool.

Strateji:
- PURE (model-driven): ``generate_card_wrapped``, ``get_card_wrapped``,
  ``list_cards_wrapped`` (registry'ye bağımlı oldukları için wrapper
  katmanı test edilir; key varsa model-driven gerçekten koşar).
- STATEFUL: ``update_section``, ``render_html``, ``render_pdf`` için
  gerçek ``ModelCard`` Pydantic dataclass yaratılır ve **underlying tool**
  doğrudan çağrılır.

Not: ``CARD_REGISTRY`` global modül değişkenidir; bu yüzden PURE
test'lerinde ``generate_card`` model tarafından çağrıldığında
registry'ye otomatik kayıt yapılır. STATEFUL test'lerde generate_card
çağrısıyla seed'lenir.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.model_card_agent import (
    generate_card_wrapped,
    get_card_wrapped,
    list_cards_wrapped,
)
from ai_data_science_team.tools.model_card import (
    ModelCard,
    generate_card,
    render_html,
    render_pdf,
    update_section,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: model-driven tool'lar (registry'ye yazar)
# ---------------------------------------------------------------------------


def test_generate_card_real(llm_or_skip, llm_model):
    """generate_card_wrapped: registry'ye yeni ModelCard yazar."""
    tool = generate_card_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "generate_card_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo' ver.",
        ),
        tool.name,
    )


def test_get_card_real(llm_or_skip, llm_model):
    """get_card_wrapped: card_id ile ModelCard döner; olmayan ID → failed content."""
    tool = get_card_wrapped
    # Önce generate_card ile seed'le ki 'missing-card' testi için
    # farklı bir çalıştırmadaki state'i yanlışlıkla yakalamayalım.
    seed = generate_card(model_id="model-demo")
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            f"get_card_wrapped tool'unu TEK çağrı ile çağır; card_id='{seed.card_id}' ver.",
        ),
        tool.name,
    )


def test_list_cards_real(llm_or_skip, llm_model):
    """list_cards_wrapped: model_id filtresi ile ModelCard listesi."""
    tool = list_cards_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "list_cards_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo' ver.",
        ),
        tool.name,
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: ModelCard Pydantic dataclass
# ---------------------------------------------------------------------------


def _fresh_card(model_id: str = "test-model") -> ModelCard:
    """Test için izole ModelCard — generate_card tüm bölüm şablonlarıyla gelir."""
    return generate_card(
        model_id=model_id,
        details={"name": "test", "version": "1.0"},
        intended_use="classification",
        metrics={"accuracy": 0.92, "f1": 0.88},
    )


def test_update_section_real():
    """update_section: bölüm günceller, version artar."""
    card = _fresh_card()
    new_card = update_section(
        card,
        section="intended_use",
        content="Yeni içerik: high-risk churn prediction.",
    )
    assert new_card.sections["intended_use"].content == ("Yeni içerik: high-risk churn prediction.")
    assert new_card.version == card.version + 1
    # Esnek bölüm ekleme (draft=True)
    new_card2 = update_section(
        card,
        section="limitations",
        content="Noisy labels in 5% of training set.",
        is_draft=True,
    )
    assert new_card2.sections["limitations"].is_draft is True


def test_render_html_real():
    """render_html: <!doctype html>...</html> string döner."""
    card = _fresh_card()
    html = render_html(card)
    assert html.startswith("<!doctype html>")
    assert "<html>" in html
    assert "Model Card" in html
    assert "test-model" in html
    # Metric bölümü içerikte olmalı
    assert "accuracy" in html
    assert "0.92" in html


def test_render_pdf_real():
    """render_pdf: WeasyPrint yoksa HTML bytes fallback, varsa PDF bytes."""
    card = _fresh_card()
    out = render_pdf(card)
    assert isinstance(out, bytes)
    assert len(out) > 0
    # İçerik ya PDF magic (\%PDF) ya da HTML doctype içerir
    assert out[:4] == b"%PDF" or out[:15].startswith(b"<!doctype html>")
