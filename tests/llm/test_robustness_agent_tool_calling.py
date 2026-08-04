"""GERÇEK robustness_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/robustness_agent.py — 4 tool.

Strateji:
- PURE (model-driven): ``default_scenarios`` model tarafından çağrılır.
- STATEFUL: ``add_gaussian_noise`` (np.ndarray), ``mask_features``
  (np.ndarray), ``evaluate_robustness`` (np.ndarray + Callable)
  tools/robustness.py doğrudan çağrılır; gerçek np.ndarray + basit predict
  callable test'te yaratılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pytest

from ai_data_science_team.agents.robustness_agent import (
    default_scenarios_wrapped,
)
from ai_data_science_team.tools.robustness import (
    add_gaussian_noise,
    evaluate_robustness,
    mask_features,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def _fresh_X() -> np.ndarray:
    """Test için taze, izole np.ndarray — gerçek numeric array."""
    return np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])


def _constant_predict(y_value: int = 1):
    """Basit predict callable: X aldığında sabit bir array döner."""

    def _predict(X):
        return np.full(X.shape[0], y_value, dtype=int)

    return _predict


# ---------------------------------------------------------------------------
# 1. PURE: default_scenarios — model-driven doğrulanabilir
# ---------------------------------------------------------------------------


def test_default_scenarios_real(llm_or_skip, llm_model):
    """``default_scenarios_wrapped(sigma_levels, mask_levels)`` spec'in default setini üretir."""
    tool = default_scenarios_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "default_scenarios tool'unu TEK çağrı ile çağır. "
            "sigma_levels=[0.05, 0.1, 0.2], mask_levels=[0.1, 0.2, 0.3].",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "scenario" in s or "noise" in s or "sigma" in s or "mask" in s or "ok" in s, (
        f"default_scenarios beklenen senaryo seti üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: np.ndarray / Callable gerektiren tool'lar — tools/robustness.py
# ---------------------------------------------------------------------------


def test_add_gaussian_noise_real():
    """add_gaussian_noise(X, *, sigma=0.1, rng=None) → X + N(0, sigma)."""
    X = _fresh_X()
    rng = np.random.default_rng(0)
    out = add_gaussian_noise(X=X, sigma=0.1, rng=rng)
    assert isinstance(out, np.ndarray)
    assert out.shape == X.shape
    # Noise eklendi: orijinal ile farklı (deterministic seed → nonzero)
    assert not np.allclose(out, X)
    # Sıfır ortalamalı gauss noise: out - X'in ortalaması ~ 0 olmalı
    diff = (out - X).astype(float)
    assert abs(diff.mean()) < 0.5  # sigma=0.1 için makul


def test_mask_features_real():
    """mask_features(X, mask_rate=0.3, *, fill_value=0.0, ...) → X'in belirli hücreleri sıfırlanır.

    3x3 matris için mask_rate=0.5 → yaklaşık yarısı 0 olmalı.
    """
    X = _fresh_X()
    rng = np.random.default_rng(0)
    out = mask_features(X=X, mask_rate=0.5, rng=rng)
    assert isinstance(out, np.ndarray)
    assert out.shape == X.shape
    # Sıfırlanan hücre sayısı 0 olmamalı
    masked_count = int((out == 0.0).sum())
    assert masked_count > 0
    # Sıfırlanmamış hücreler orijinal değerleri korumalı
    nonzero_pos = np.argwhere(out != 0.0)
    for i, j in nonzero_pos:
        assert out[i, j] == X[i, j]


def test_evaluate_robustness_real():
    """evaluate_robustness(model_name, predict, X, y, *, ...) → RobustnessResult.

    Constant predict callable ile default scenario'lar çalıştırılır;
    summary DataFrame'i scenario adlarına göre indekslenmiş olmalı.
    """
    X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    y = np.array([0, 1, 0])
    predict = _constant_predict(y_value=1)

    out = evaluate_robustness(
        model_name="m1",
        predict=predict,
        X=X,
        y=y,
        replicates=1,
        metric="accuracy",
    )
    # RobustnessResult dataclass: matrix (DataFrame) + summary (DataFrame)
    assert hasattr(out, "matrix") and hasattr(out, "summary")
    assert out.model_name == "m1"
    assert out.metric == "accuracy"
    # summary scenario adlarına göre indekslenmiş
    scenario_names = list(out.summary.index)
    assert "clean" in scenario_names
    # clean scenario: predict(X) = [1,1,1] vs y=[0,1,0] → accuracy = 1/3
    clean_acc = float(out.summary.loc["clean", "mean"])
    assert abs(clean_acc - (1.0 / 3.0)) < 1e-9
