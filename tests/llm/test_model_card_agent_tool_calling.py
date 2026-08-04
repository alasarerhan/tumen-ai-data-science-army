"""GERÇEK model-driven model_card_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.model_card_agent import (
    generate_card_wrapped,
    get_card_wrapped,
    list_cards_wrapped,
    render_html_wrapped,
    render_pdf_wrapped,
    update_section_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_generate_card_real(llm_or_skip, llm_model):
    tool = generate_card_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "generate_card_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo' ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_get_card_real(llm_or_skip, llm_model):
    tool = get_card_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "get_card_wrapped tool'unu TEK çağrı ile çağır; card_id='missing-card' ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_list_cards_real(llm_or_skip, llm_model):
    tool = list_cards_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "list_cards_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo' ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_update_section_stateful_skipped():
    assert hasattr(update_section_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_render_html_stateful_skipped():
    assert hasattr(render_html_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")


def test_render_pdf_stateful_skipped():
    assert hasattr(render_pdf_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
