"""GERÇEK test champion_challenger_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/champion_challenger_agent.py — 5 tool.

Strateji:
- Tüm 5 tool (mcnemar_test, wilcoxon_signed_rank, auc_with_delong_ci,
  delong_pvalue, compare_models) PURE'dur → model-driven _drive_tool_call.
  Wrapper kwargs eşleşmeleri doğru; underlying tool hatasız çalışır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.champion_challenger_agent import (
    auc_with_delong_ci_wrapped,
    compare_models_wrapped,
    delong_pvalue_wrapped,
    mcnemar_test_wrapped,
    wilcoxon_signed_rank_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. mcnemar_test_wrapped
# ---------------------------------------------------------------------------


def test_mcnemar_test_real(llm_or_skip, llm_model):
    """mcnemar_test: paired binary classification disagreement test."""
    tool = mcnemar_test_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "mcnemar_test tool'unu TEK çağrı ile çağır. "
            "y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "
            "y_pred_a=[0, 1, 0, 1, 0, 0, 0, 1, 0, 1], "
            "y_pred_b=[0, 1, 1, 1, 0, 1, 0, 1, 0, 0], "
            "exact=false, correction=true.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "mcnemar" in s or "ok" in s or "p_value" in s or "statistic" in s, (
        f"mcnemar_test beklenen test istatistiği üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. wilcoxon_signed_rank_wrapped
# ---------------------------------------------------------------------------


def test_wilcoxon_signed_rank_real(llm_or_skip, llm_model):
    """wilcoxon_signed_rank: paired residual comparison."""
    tool = wilcoxon_signed_rank_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "wilcoxon_signed_rank tool'unu TEK çağrı ile çağır. "
            "residuals_a=[0.1, -0.2, 0.3, -0.1, 0.4, -0.3, 0.2, -0.1], "
            "residuals_b=[0.05, -0.1, 0.2, -0.05, 0.25, -0.2, 0.15, -0.05], "
            'alternative="two-sided".',
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "wilcoxon" in s or "ok" in s or "p_value" in s or "statistic" in s, (
        f"wilcoxon beklenen test istatistiği üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 3. auc_with_delong_ci_wrapped
# ---------------------------------------------------------------------------


def test_auc_with_delong_ci_real(llm_or_skip, llm_model):
    """auc_with_delong_ci: AUC + DeLong 95% CI."""
    tool = auc_with_delong_ci_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "auc_with_delong_ci tool'unu TEK çağrı ile çağır. "
            "y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "
            "scores=[0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.45, 0.55], "
            "alpha=0.05.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "auc" in s or "ok" in s or "ci" in s or "delong" in s, (
        f"auc_with_delong_ci beklenen AUC üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 4. delong_pvalue_wrapped
# ---------------------------------------------------------------------------


def test_delong_pvalue_real(llm_or_skip, llm_model):
    """delong_pvalue: p-value for two AUC comparison."""
    tool = delong_pvalue_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "delong_pvalue tool'unu TEK çağrı ile çağır. "
            "y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "
            "scores_a=[0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.45, 0.55], "
            "scores_b=[0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.5, 0.5, 0.4, 0.6].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "p_value" in s or "ok" in s or "delong" in s, (
        f"delong_pvalue beklenen p-value üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 5. compare_models_wrapped
# ---------------------------------------------------------------------------


def test_compare_models_real(llm_or_skip, llm_model):
    """compare_models: end-to-end model comparison."""
    tool = compare_models_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "compare_models tool'unu TEK çağrı ile çağır. "
            "y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1], "
            "y_proba_a=[0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.45, 0.55, 0.5, 0.5], "
            "y_proba_b=[0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.5, 0.5, 0.4, 0.6, 0.45, 0.55].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "compare" in s or "ok" in s or "decision" in s or "compar" in s, (
        f"compare_models beklenen karar yapısı üretmedi: {s[:200]}"
    )
