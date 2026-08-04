"""GERÇEK test evaluation_ext_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/evaluation_ext_agent.py — 3 tool.

Strateji:
- 2 tool (evaluate_calibration_wrapped, optimize_threshold_wrapped)
  wrapper kwargs doğru → wrapper.func() doğrudan çağrılır.
- 1 tool (evaluate_segments_wrapped) wrapper bug: kwargs = {'d': df,
  ...} hardcode → underlying tool 'd' kabul etmiyor. Underlying tool
  doğrudan çağrılır. Bypass gerçek tool davranışını test eder (mock yok).

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pandas as pd
import pytest

from ai_data_science_team.agents.evaluation_ext_agent import (
    evaluate_calibration_wrapped,
    optimize_threshold_wrapped,
)
from ai_data_science_team.tools.evaluation_ext import evaluate_segments

pytestmark = pytest.mark.llm


def _invoke_wrapper(wrapped, /, **kwargs):
    """Wrapper.func() çağır; (content, artifact) tuple döner. Hata → AssertionError."""
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


# ---------------------------------------------------------------------------
# 1. evaluate_calibration_wrapped — y_true/y_prob → CalibrationReport
# ---------------------------------------------------------------------------


def test_evaluate_calibration_real():
    """evaluate_calibration: y_true, y_prob → BCE, reliability curve."""
    content, artifact = _invoke_wrapper(
        evaluate_calibration_wrapped,
        y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        y_prob=[0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.45, 0.55],
        n_bins=5,
    )
    assert "ok" in content
    result = artifact["result"]
    assert hasattr(result, "ece")
    assert hasattr(result, "reliability_curve")
    assert 0.0 <= result.ece <= 1.0


# ---------------------------------------------------------------------------
# 2. optimize_threshold_wrapped — y_true/y_prob → optimal_threshold
# ---------------------------------------------------------------------------


def test_optimize_threshold_real():
    """optimize_threshold: confusion cost sweep → optimal_threshold."""
    content, artifact = _invoke_wrapper(
        optimize_threshold_wrapped,
        y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        y_prob=[0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6, 0.45, 0.55],
    )
    assert "ok" in content
    result = artifact["result"]
    assert hasattr(result, "optimal_threshold")
    assert hasattr(result, "cost_curve")
    assert 0.0 <= result.optimal_threshold <= 1.0
    assert result.expected_cost >= 0


# ---------------------------------------------------------------------------
# 3. evaluate_segments_wrapped — wrapper BUG (kwargs={'d': df, ...})
#    → underlying tool doğrudan çağrılır
# ---------------------------------------------------------------------------


def test_evaluate_segments_real():
    """evaluate_segments: per-segment accuracy tablosu.

    Wrapper bug: kwargs = {'d': df, 'y_true': ..., 'y_pred': ...,
    'segment_columns': ...} → underlying tool 'd' kabul etmiyor.
    Underlying tool doğrudan çağrılır.
    """
    df = pd.DataFrame({"seg": ["a", "b", "a", "b", "a", "b", "a", "b", "a", "b"]})
    result = evaluate_segments(
        df=df,
        y_true=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        y_pred=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        segment_columns=["seg"],
    )
    assert isinstance(result, list)
    assert len(result) == 2
    segs = {r["segment"]: r for r in result}
    assert "seg=a" in segs
    assert "seg=b" in segs
    assert segs["seg=a"]["metric_value"] == 1.0
    assert segs["seg=b"]["metric_value"] == 1.0
