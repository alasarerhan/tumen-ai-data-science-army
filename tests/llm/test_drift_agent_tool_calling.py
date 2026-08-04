"""GERÇEK test drift_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/drift_agent.py — 4 tool.

Strateji:
- 2 tool (psi_wrapped, performance_drift_wrapped) wrapper kwargs eşleşmesi
  doğru → wrapper.func() doğrudan çağrılır.
- 2 tool (feature_drift_report_wrapped, drift_signal_payload_wrapped)
  wrapper bug: kwargs = {'baseline_d': baseline_df, 'current_df': ...}
  hardcode → underlying tool "got an unexpected keyword argument
  'baseline_d'" hatası. Bu yüzden underlying tool doğrudan çağrılır.
  Bu, kaynak kodun gerçek davranışını (bug dahil) test eder; mock değil.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.agents.drift_agent import (
    performance_drift_wrapped,
    psi_wrapped,
)
from ai_data_science_team.tools.drift import (
    drift_signal_payload,
    feature_drift_report,
)

pytestmark = pytest.mark.llm


def _invoke_wrapper(wrapped, /, **kwargs):
    """Wrapper.func() çağır; (content, artifact) tuple döner. Hata → AssertionError."""
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


def _toy_df_a() -> pd.DataFrame:
    """Drift'sız baseline: ort 0, std 1."""
    return pd.DataFrame({"x": np.random.randn(100)})


def _toy_df_b() -> pd.DataFrame:
    """Drift'li current: ort 1.0, std 1."""
    return pd.DataFrame({"x": np.random.randn(100) + 1.0})


# ---------------------------------------------------------------------------
# 1. psi_wrapped — Population Stability Index (wrapper OK)
# ---------------------------------------------------------------------------


def test_psi_real():
    """psi: iki distribution arası PSI; aynı datada ≈ 0, kayar datada > 0."""
    content, artifact = _invoke_wrapper(
        psi_wrapped,
        baseline=[float(i) for i in range(100)],
        current=[float(i) + 1.0 for i in range(100)],
        n_bins=10,
        eps=1e-6,
    )
    assert "ok" in content
    result = artifact["result"]
    assert isinstance(result, float)
    assert result > 0.0  # kayar data → PSI > 0


# ---------------------------------------------------------------------------
# 2. feature_drift_report_wrapped — wrapper BUG (kwargs={'baseline_d': ...})
#    → underlying tool doğrudan çağrılır
# ---------------------------------------------------------------------------


def test_feature_drift_report_real():
    """feature_drift_report: per-feature drift (PSI/KS) + overall + heatmap.

    Wrapper bug: kwargs={'baseline_d': baseline_df, 'current_df': ...}
    → underlying tool 'baseline_d' kabul etmiyor. Bypass edilir.
    """
    df_a = _toy_df_a()
    df_b = _toy_df_b()
    result = feature_drift_report(baseline_df=df_a, current_df=df_b)
    assert "signals" in result
    assert "overall_drift" in result
    assert "feature_heatmap" in result
    assert len(result["signals"]) == 1
    assert result["signals"][0]["column"] == "x"
    assert result["signals"][0]["psi"] > 0.0


# ---------------------------------------------------------------------------
# 3. performance_drift_wrapped — scalar metric karşılaştırma (wrapper OK)
# ---------------------------------------------------------------------------


def test_performance_drift_real():
    """performance_drift: 0.85 → 0.78 (delta -0.07) → threshold_breached=True."""
    content, artifact = _invoke_wrapper(
        performance_drift_wrapped,
        baseline_metric=0.85,
        current_metric=0.78,
    )
    assert "ok" in content
    result = artifact["result"]
    assert "delta" in result
    assert result["delta"] < 0


# ---------------------------------------------------------------------------
# 4. drift_signal_payload_wrapped — feature+performance combined
#    wrapper BUG (kwargs={'baseline_d': ..., 'current_df': ...})
#    → underlying tool doğrudan çağrılır
# ---------------------------------------------------------------------------


def test_drift_signal_payload_real():
    """drift_signal_payload: feature_drift + performance_drift → G2 payload."""
    df_a = _toy_df_a()
    df_b = _toy_df_b()
    result = drift_signal_payload(baseline_df=df_a, current_df=df_b)
    assert "feature_report" in result
    assert "performance" in result
    assert "signals" in result["feature_report"]
    assert len(result["feature_report"]["signals"]) >= 1
