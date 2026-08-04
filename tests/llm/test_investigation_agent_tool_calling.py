"""GERÇEK model-driven investigation_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.investigation_agent import (
    detect_change_wrapped,
    investigate_wrapped,
    isolate_dimension_wrapped,
    narrate_wrapped,
    quantify_contributors_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_detect_change_real(llm_or_skip, llm_model):
    tool = detect_change_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "detect_change_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_isolate_dimension_real(llm_or_skip, llm_model):
    tool = isolate_dimension_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "isolate_dimension_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_quantify_contributors_real(llm_or_skip, llm_model):
    tool = quantify_contributors_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "quantify_contributors_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_narrate_real(llm_or_skip, llm_model):
    tool = narrate_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "narrate_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_investigate_real(llm_or_skip, llm_model):
    tool = investigate_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "investigate_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None
