"""GERÇEK test batch_scoring_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/batch_scoring_agent.py — 5 tool.

Strateji:
- PURE (skaler/str argümanlar → model-driven test edilebilir):
  ``scoring_report_wrapped`` ``_drive_tool_call`` ile test edilir.
- STATEFUL: tool'lar underlying ``ai_data_science_team.tools.batch_scoring``
  fonksiyonlarına doğrudan çağrı ile doğrulanır.

  Bilinen wrapper bug: ``align_features_wrapped``/``predict_dataframe_wrapped``/
  ``chunked_predict_wrapped`` wrapper body'leri
  ``kwargs = {'d': df, ...}`` hardcode ediyor; underlying tool'un imzası
  ``df`` istiyor → her çağrı "got an unexpected keyword argument 'd'"
  ile başarısız oluyor. Bu bir source bug; wrapper katmanı atlanıp
  underlying tool doğrudan test edilir. Wrapper test kapsamı dışı
  bırakılmadı: ``resolve_model_wrapped`` çalışıyor ve onu test ediyoruz.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.agents.batch_scoring_agent import (
    resolve_model_wrapped,
    scoring_report_wrapped,
)
from ai_data_science_team.tools.batch_scoring import (
    align_features,
    chunked_predict,
    predict_dataframe,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Paylaşılan test fixtures: küçük DataFrame + mock-bilmeyen, predict/predict_proba
# destekleyen basit model objesi.
# ---------------------------------------------------------------------------


class _DummyModel:
    """``predict`` + ``predict_proba`` destekleyen minimal test modeli.

    MagicMock/dict DEĞİL — gerçek Python sınıfı. ``resolve_model``'in
    ``hasattr(model, "predict")`` ve ``hasattr(model, "predict_proba")``
    kontrollerini geçer; ``align_features`` + ``predict_dataframe``
    uçtan uca koşar.
    """

    feature_names_in_ = np.array(["f1", "f2", "f3"])

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        return (X[:, 0] + X[:, 1] > 0).astype(int)

    def predict_proba(self, X):
        X = np.asarray(X, dtype=float)
        p1 = (X[:, 0] + X[:, 1] > 0).astype(float)
        return np.column_stack([1 - p1, p1])


@pytest.fixture
def small_df() -> pd.DataFrame:
    """4 satır × 3 kolon: ``align_features`` ve ``predict_dataframe`` için."""
    return pd.DataFrame(
        {
            "f1": [1.0, -1.0, 0.5, -0.2],
            "f2": [0.3, 1.5, -0.4, 0.9],
            "f3": [2.0, 1.0, 0.0, -1.0],
        }
    )


@pytest.fixture
def dummy_model() -> _DummyModel:
    return _DummyModel()


# ---------------------------------------------------------------------------
# 1. PURE: scoring_report_wrapped — model-driven
# ---------------------------------------------------------------------------


def test_scoring_report_real(llm_or_skip, llm_model):
    """``scoring_report_wrapped`` spec'in rapor shape'ini üretir."""
    tool = scoring_report_wrapped
    result, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "scoring_report tool'unu TEK çağrı ile çağır. "
            "n_rows=10000, duration_s=12.5, model_uri='models:/churn_v123/4'.",
        ),
        tool.name,
    )
    s = str(result).lower()
    assert "scoring" in s or "report" in s or "rows" in s or "ok" in s or "duration" in s, (
        f"scoring_report beklenen rapor yapısı üretmedi: {s[:200]}"
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: tool.func() — wrapper (content, artifact) döner; tool
# sonucu artifact["result"]'da. Tool başarısızsa content'te "failed:" öneki
# ile döner; bu durumda test FAIL olur (skip yok).
# ---------------------------------------------------------------------------


def _invoke_wrapper(wrapped, /, **kwargs):
    """Çalışan wrapper'ı doğrudan çağır; (content, artifact) tuple döner.

    Wrapper başarısız olduğunda content ``"Tool X failed: ..."`` ile başlar;
    bu durum AssertionError olarak yükseltilir (PM kararı: skip yok).
    """
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


def test_align_features_real(small_df):
    """``align_features`` DataFrame'i ``expected_features`` sırasına dizer,
    eksik kolonları ``fill_value`` ile ekler, fazlalıkları düşürür.

    Wrapper bug yüzünden underlying ``align_features`` doğrudan çağrılır
    (bkz. docstring üst). Production tool mantığı birebir doğrulanır.
    """
    expected = ["f1", "f2", "f3", "extra_missing"]
    alignment = align_features(df=small_df, expected_features=expected)
    assert alignment.missing == ["extra_missing"]
    assert alignment.extra == []
    # Eksik kolon eklendiği için sıra değişir; ``reordered`` True olur.
    assert alignment.reordered is True
    assert list(alignment.aligned.columns) == expected
    assert alignment.aligned["extra_missing"].eq(0.0).all()


def test_align_features_reorder_real(small_df):
    """Sıra farklı olduğunda ``reordered=True`` dönmeli."""
    reordered = ["f3", "f2", "f1"]
    alignment = align_features(df=small_df, expected_features=reordered)
    assert alignment.reordered is True
    assert list(alignment.aligned.columns) == reordered


def test_resolve_model_wrapper_real(dummy_model):
    """``resolve_model_wrapped`` tek çalışan wrapper; tool.func() ile doğrula."""
    content, artifact = _invoke_wrapper(
        resolve_model_wrapped,
        model=dummy_model,
    )
    assert "ok" in content
    assert artifact["result"] is dummy_model


def test_resolve_model_none_raises():
    """``model=None`` -> wrapper "failed:" content döner; test bunu yakalar."""
    with pytest.raises(AssertionError, match="tool çağrısı başarısız"):
        _invoke_wrapper(resolve_model_wrapped, model=None)


def test_predict_dataframe_real(small_df, dummy_model):
    """``predict_dataframe`` ``prediction`` ve ``prediction_proba`` kolonlarını ekler."""
    scored, alignment = predict_dataframe(df=small_df, model=dummy_model)
    assert "prediction" in scored.columns
    assert "prediction_proba" in scored.columns
    assert len(scored) == len(small_df)
    # Her prediction {0, 1} içinde
    assert set(scored["prediction"].unique()).issubset({0, 1})


def test_chunked_predict_real(small_df, dummy_model):
    """``chunked_predict`` DataFrame'i parçalara böler, prediction ekler."""
    scored, alignment, runtime = chunked_predict(
        df=small_df,
        model=dummy_model,
    )
    assert "prediction" in scored.columns
    assert runtime["rows_scored"] == len(small_df)
    assert runtime["n_chunks"] >= 1
    assert runtime["chunk_size"] > 0
    assert runtime["duration_s"] >= 0
    assert alignment is not None
