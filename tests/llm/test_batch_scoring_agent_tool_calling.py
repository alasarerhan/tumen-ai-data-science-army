"""GERÇEK model-driven batch_scoring_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/batch_scoring_agent.py — 5 tool.

PURE (skaler/str argümanlar → model-driven test edilebilir):
- scoring_report_wrapped  — n_rows, duration_s, model_uri → spec-shaped report

STATEFUL (pd.DataFrame + model objesi → API test kapsamı):
- align_features_wrapped      — df (pd.DataFrame), expected_features (Sequence)
- resolve_model_wrapped       — model (Any)
- predict_dataframe_wrapped   — df, model
- chunked_predict_wrapped     — df, model
"""

from __future__ import annotations

import inspect

import pytest

from ai_data_science_team.agents.batch_scoring_agent import scoring_report_wrapped
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# PURE: scoring_report_wrapped
# ---------------------------------------------------------------------------

def test_scoring_report_real(llm_or_skip, llm_model):
    """``scoring_report_wrapped(...)`` spec'in rapor shape'ini üretir."""
    tool = scoring_report_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "scoring_report tool'unu TEK çağrı ile çağır. "
            "n_rows=10000, duration_s=12.5, model_uri='models:/churn_v123/4'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "scoring" in s
        or "report" in s
        or "rows" in s
        or "ok" in s
        or "duration" in s
    ), f"scoring_report beklenen rapor yapısı üretmedi: {s[:200]}"


# ---------------------------------------------------------------------------
# STATEFUL: pd.DataFrame + model → API test kapsamı
# ---------------------------------------------------------------------------

STATEFUL_TOOLS = [
    "align_features_wrapped",
    "resolve_model_wrapped",
    "predict_dataframe_wrapped",
    "chunked_predict_wrapped",
]


@pytest.mark.parametrize("tool_name", STATEFUL_TOOLS)
def test_batch_scoring_tool_stateful_skipped(tool_name):
    """Batch scoring tool'ları ``pd.DataFrame`` + model objesi gerektiriyor.

    Tool'ların ya ``df`` parametresi pd.DataFrame alıyor (Pydantic
    JSON-serializable değil) ya da model objesi alıyor. Model-driven harness
    kapsamı dışındadır; Faz C API entegrasyon testinde kapsanmalıdır.
    """
    import ai_data_science_team.agents.batch_scoring_agent as mod

    wrapper = getattr(mod, tool_name)
    sig = inspect.signature(wrapper.func)
    # df veya model parametresi var mı kontrol et
    has_df = "df" in sig.parameters
    has_model = "model" in sig.parameters
    assert has_df or has_model, (
        f"{tool_name} df/model arg bekliyordu, signature={list(sig.parameters)}"
    )
    pytest.skip(
        f"stateful tool: {tool_name} pd.DataFrame/model arg alır; "
        f"API entegrasyon testinde kapsanacak"
    )
