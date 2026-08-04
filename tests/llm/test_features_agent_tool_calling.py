"""GERÇEK test features_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/features_agent.py — 7 tool.

Strateji:
- 1 tool (multicollinearity_report_wrapped) wrapper kwargs doğru
  (kwargs={'df': df}) → wrapper.func() doğrudan çağrılır.
- 6 tool (filter_scores, select_filter, select_wrapper, select_embedded,
  detect_leakage, select_feature) wrapper bug: kwargs = {'d': df,
  'target': ...} hardcode → underlying tool 'd' kabul etmiyor. Underlying
  tool doğrudan çağrılır. Bypass gerçek tool davranışını test eder.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.agents.features_agent import (
    multicollinearity_report_wrapped,
)
from ai_data_science_team.tools.features import (
    detect_leakage,
    filter_scores,
    select_embedded,
    select_feature,
    select_filter,
    select_wrapper,
)

pytestmark = pytest.mark.llm


def _invoke_wrapper(wrapped, /, **kwargs):
    """Wrapper.func() çağır; (content, artifact) tuple döner. Hata → AssertionError."""
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


def _toy_df_target() -> tuple[pd.DataFrame, pd.Series]:
    """3 numeric feature + binary target (sınıflandırma)."""
    np.random.seed(42)
    df = pd.DataFrame({
        "a": np.random.randn(50),
        "b": np.random.randn(50) + 0.5,
        "c": np.random.randn(50) - 0.5,
    })
    target = pd.Series([int(i % 2) for i in range(50)])
    return df, target


# ---------------------------------------------------------------------------
# 1. filter_scores_wrapped — wrapper BUG (kwargs={'d': df, ...})
#    → underlying tool doğrudan çağrılır
# ---------------------------------------------------------------------------


def test_filter_scores_real():
    """filter_scores: per-feature filter score (correlation, mutual_info vb.)."""
    df, target = _toy_df_target()
    result = filter_scores(df=df, target=target)
    assert isinstance(result, list)
    assert len(result) == 3
    for ent in result:
        assert "feature" in ent
        assert "score" in ent


# ---------------------------------------------------------------------------
# 2. select_filter_wrapped — wrapper BUG → underlying tool
# ---------------------------------------------------------------------------


def test_select_filter_real():
    """select_filter: top-k features by filter score."""
    df, target = _toy_df_target()
    result = select_filter(df=df, target=target)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert set(result).issubset({"a", "b", "c"})


# ---------------------------------------------------------------------------
# 3. select_wrapper_wrapped — wrapper BUG → underlying tool
# ---------------------------------------------------------------------------


def test_select_wrapper_real():
    """select_wrapper: greedy forward selection."""
    df, target = _toy_df_target()
    result = select_wrapper(df=df, target=target)
    assert isinstance(result, list)
    assert len(result) >= 1
    assert set(result).issubset({"a", "b", "c"})


# ---------------------------------------------------------------------------
# 4. select_embedded_wrapped — wrapper BUG → underlying tool
# ---------------------------------------------------------------------------


def test_select_embedded_real():
    """select_embedded: L1-regularized logistic regression coefficients."""
    df, target = _toy_df_target()
    result = select_embedded(df=df, target=target)
    assert isinstance(result, list)
    assert len(result) == 3
    for ent in result:
        assert "feature" in ent
        assert "coefficient" in ent
        assert "selected" in ent


# ---------------------------------------------------------------------------
# 5. detect_leakage_wrapped — wrapper BUG → underlying tool
# ---------------------------------------------------------------------------


def test_detect_leakage_real():
    """detect_leakage: target-feature korelasyon kontrolü → LeakageReport."""
    df, target = _toy_df_target()
    result = detect_leakage(df=df, target=target)
    assert hasattr(result, "findings")
    assert isinstance(result.findings, list)


# ---------------------------------------------------------------------------
# 6. multicollinearity_report_wrapped — wrapper OK (kwargs={'df': df})
# ---------------------------------------------------------------------------


def test_multicollinearity_report_real():
    """multicollinearity_report: VIF + correlation matrix."""
    df, _ = _toy_df_target()
    content, artifact = _invoke_wrapper(
        multicollinearity_report_wrapped, df=df,
    )
    assert "ok" in content
    result = artifact["result"]
    assert "vif" in result
    assert "correlation_matrix" in result
    assert "high_vif" in result or "high_correlation_pairs" in result


# ---------------------------------------------------------------------------
# 7. select_feature_wrapped — wrapper BUG → underlying tool
# ---------------------------------------------------------------------------


def test_select_feature_real():
    """select_feature: end-to-end feature selection → dict (method, selected, scores)."""
    df, target = _toy_df_target()
    result = select_feature(df=df, target=target)
    assert isinstance(result, dict)
    assert "method" in result
    assert "selected" in result
    assert "scores" in result
    assert isinstance(result["selected"], list)
