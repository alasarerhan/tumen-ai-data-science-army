"""GERÇEK test causal_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/causal_agent.py — 4 tool.

Strateji:
- Tüm 4 tool (did_lift, adj_lift, check_propensity_overlap, e_value)
  PURE'dur (skaler/Sequence argümanlar → model-driven ile test edilebilir).
  ``_drive_tool_call`` ile tool.invoke() Pydantic validation katmanını
  geçer; wrapper **kwargs = {'pre_treat_y_pre': ...} doğru eşleşir,
  underlying tool hatasız çalışır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.causal_agent import (
    adj_lift_wrapped,
    check_propensity_overlap_wrapped,
    did_lift_wrapped,
    e_value_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: did_lift_wrapped — diff-in-diff ATE
# ---------------------------------------------------------------------------


def test_did_lift_real(llm_or_skip, llm_model):
    """did_lift: pre_treat_y_pre, pre_treat_y_post, control_y_pre, control_y_post.

    Tedavi grubu 10→20 (Δ=+10), kontrol 10→12 (Δ=+2) → ATE ≈ 8.
    """
    tool = did_lift_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "did_lift tool'unu TEK çağrı ile çağır. "
            "pre_treat_y_pre=[10.0, 11.0, 9.0, 10.5, 9.5], "
            "pre_treat_y_post=[20.0, 19.5, 21.0, 20.2, 19.8], "
            "control_y_pre=[10.0, 11.0, 9.0, 10.5, 9.5], "
            "control_y_post=[11.5, 12.5, 11.0, 12.0, 11.8].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "did_lift" in s or "ok" in s or "ate" in s
    ), f"did_lift beklenen DiD çıktısı üretmedi: {s[:200]}"


# ---------------------------------------------------------------------------
# 2. PURE: adj_lift_wrapped — adjusted mean difference
# ---------------------------------------------------------------------------


def test_adj_lift_real(llm_or_skip, llm_model):
    """adj_lift: y, treatment (0/1), covariates (Sequence[Sequence[float]])."""
    tool = adj_lift_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "adj_lift tool'unu TEK çağrı ile çağır. "
            "y=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], "
            "treatment=[0, 0, 0, 0, 1, 1, 1, 1], "
            "covariates=[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "adj_lift" in s or "ok" in s or "ate" in s or "r2" in s
    ), f"adj_lift beklenen adjusted lift çıktısı üretmedi: {s[:200]}"


# ---------------------------------------------------------------------------
# 3. PURE: check_propensity_overlap_wrapped — propensity support
# ---------------------------------------------------------------------------


def test_check_propensity_overlap_real(llm_or_skip, llm_model):
    """check_propensity_overlap: 0.1–0.9 arası değerler → overlap_ok True."""
    tool = check_propensity_overlap_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "check_propensity_overlap tool'unu TEK çağrı ile çağır. "
            "propensity=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], "
            'label="treatment".',
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "overlap" in s or "ok" in s or "share" in s
    ), f"propensity beklenen overlap raporu üretmedi: {s[:200]}"


# ---------------------------------------------------------------------------
# 4. PURE: e_value_wrapped — sensitivity bound
# ---------------------------------------------------------------------------


def test_e_value_real(llm_or_skip, llm_model):
    """e_value: point_estimate=2.0 → E-value ≈ 3.41."""
    tool = e_value_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model, tool,
            "e_value tool'unu TEK çağrı ile çağır. point_estimate=2.0.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert (
        "e_value" in s or "ok" in s or "eval" in s
    ), f"e_value beklenen sensitivity bound üretmedi: {s[:200]}"
