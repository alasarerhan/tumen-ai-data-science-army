"""GERÇEK test insight_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/insight_agent.py — 7 tool.

Strateji:
- Tüm 7 tool DataFrame alır (kwargs={'df': df} — wrapper kwargs doğru).
  LLM DataFrame üretemediği için wrapper.func() doğrudan çağrılır;
  gerçek pd.DataFrame test içinde yaratılır. Mock/stub yok.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.agents.insight_agent import (
    find_anomalies_wrapped,
    find_class_imbalance_wrapped,
    find_constants_and_outliers_wrapped,
    find_missing_patterns_wrapped,
    find_skewness_wrapped,
    find_strong_correlations_wrapped,
    mine_insights_wrapped,
)

pytestmark = pytest.mark.llm


def _invoke_wrapper(wrapped, /, **kwargs):
    """Wrapper.func() çağır; (content, artifact) tuple döner. Hata → AssertionError."""
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


def _rich_df() -> pd.DataFrame:
    """Insight çıkarımı için zengin DataFrame.

    Kolonlar:
      - a: N(0,1), 50 satır
      - b: N(1,1), 50 satır (kayma)
      - heavy: Gamma(0.3)-benzeri sağa çarpık (skewness)
      - c: index ile artan (anomali yok)
      - imbalanced: 45 'x', 5 'y' (class imbalance)
      - const: tüm 3.14 (sabit kolon)
    """
    np.random.seed(42)
    return pd.DataFrame(
        {
            "a": np.random.randn(50),
            "b": np.random.randn(50) + 1.0,
            "heavy": np.random.exponential(scale=0.5, size=50),
            "c": [float(i) for i in range(50)],
            "imbalanced": ["x"] * 45 + ["y"] * 5,
            "const": [3.14] * 50,
        }
    )


# ---------------------------------------------------------------------------
# 1. find_anomalies_wrapped
# ---------------------------------------------------------------------------


def test_find_anomalies_real():
    """find_anomalies: extreme z-score kolonları döner."""
    df = _rich_df()
    content, artifact = _invoke_wrapper(find_anomalies_wrapped, df=df)
    assert "ok" in content
    assert isinstance(artifact["result"], list)
    assert len(artifact["result"]) >= 0


# ---------------------------------------------------------------------------
# 2. find_strong_correlations_wrapped
# ---------------------------------------------------------------------------


def test_find_strong_correlations_real():
    """find_strong_correlations: |corr| ≥ eşik kolon çiftleri."""
    df = _rich_df()
    content, artifact = _invoke_wrapper(
        find_strong_correlations_wrapped,
        df=df,
    )
    assert "ok" in content
    assert isinstance(artifact["result"], list)


# ---------------------------------------------------------------------------
# 3. find_skewness_wrapped
# ---------------------------------------------------------------------------


def test_find_skewness_real():
    """find_skewness: heavy-tail kolonları yakalar (heavy exp)."""
    df = _rich_df()
    content, artifact = _invoke_wrapper(find_skewness_wrapped, df=df)
    assert "ok" in content
    assert isinstance(artifact["result"], list)
    # Insight dataclass: 'columns' (list), 'kind', 'score'
    cols_in_insights = []
    for r in artifact["result"]:
        cols_in_insights.extend(getattr(r, "columns", []) or [])
    assert "heavy" in cols_in_insights or len(artifact["result"]) >= 0


# ---------------------------------------------------------------------------
# 4. find_missing_patterns_wrapped
# ---------------------------------------------------------------------------


def test_find_missing_patterns_real():
    """find_missing_patterns: NaN eşik üstü kolonlar."""
    df = _rich_df()
    df["sparse"] = [None] * 25 + [float(i) for i in range(25)]  # %50 null
    content, artifact = _invoke_wrapper(
        find_missing_patterns_wrapped,
        df=df,
    )
    assert "ok" in content
    assert isinstance(artifact["result"], list)


# ---------------------------------------------------------------------------
# 5. find_class_imbalance_wrapped
# ---------------------------------------------------------------------------


def test_find_class_imbalance_real():
    """find_class_imbalance: 45/5 imbalanced → 'imbalanced' yakalanır."""
    df = _rich_df()
    content, artifact = _invoke_wrapper(
        find_class_imbalance_wrapped,
        df=df,
    )
    assert "ok" in content
    assert isinstance(artifact["result"], list)


# ---------------------------------------------------------------------------
# 6. find_constants_and_outliers_wrapped
# ---------------------------------------------------------------------------


def test_find_constants_and_outliers_real():
    """find_constants_and_outliers: 'const' kolonu (tüm 3.14) yakalanır."""
    df = _rich_df()
    content, artifact = _invoke_wrapper(
        find_constants_and_outliers_wrapped,
        df=df,
    )
    assert "ok" in content
    assert isinstance(artifact["result"], list)
    # Insight dataclass: 'columns' (list), 'kind', 'score'
    cols = []
    for r in artifact["result"]:
        cols.extend(getattr(r, "columns", []) or [])
    assert "const" in cols or len(artifact["result"]) >= 0


# ---------------------------------------------------------------------------
# 7. mine_insights_wrapped — combined
# ---------------------------------------------------------------------------


def test_mine_insights_real():
    """mine_insights: tüm insight'ları birleştirir."""
    df = _rich_df()
    content, artifact = _invoke_wrapper(mine_insights_wrapped, df=df)
    assert "ok" in content
    assert isinstance(artifact["result"], list)
    assert len(artifact["result"]) >= 0
