"""GERÇEK test data_diff_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/data_diff_agent.py — 6 tool.

Strateji:
- Tüm tool'lar DataFrame/Series alır (pd.DataFrame, pd.Series). LLM bu
  argümanları JSON olarak üretemez (pydantic "is_instance_of DataFrame"
  hatası). Bu yüzden tool.func() doğrudan çağrılır; gerçek pd.DataFrame
  test içinde yaratılır, mock/stub kullanılmaz.
  Wrapper kwargs eşleşmeleri doğru (kwargs={'df': df}, kwargs={'left':
  pd.Series, 'right': pd.Series} vb.) — tool.func() çağrısı underlying
  tool'u doğru argümanlarla çalıştırır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai_data_science_team.agents.data_diff_agent import (
    diff_payload_wrapped,
    diff_summary_wrapped,
    key_set_diff_wrapped,
    numeric_shift_wrapped,
    profile_columns_wrapped,
    schema_delta_wrapped,
)

pytestmark = pytest.mark.llm


def _invoke_wrapper(wrapped, /, **kwargs):
    """Wrapper.func() çağır; (content, artifact) tuple döner. Hata → AssertionError."""
    content, artifact = wrapped.func(**kwargs)
    if isinstance(content, str) and content.startswith("Tool ") and "failed:" in content:
        raise AssertionError(f"tool çağrısı başarısız: {content!r}")
    return content, artifact


def _toy_df_a() -> pd.DataFrame:
    """Sol taraf: 20 satır, 3 kolon (id, value, label)."""
    return pd.DataFrame(
        {
            "id": list(range(20)),
            "value": np.arange(20, dtype=float),
            "label": ["a" if i % 2 == 0 else "b" for i in range(20)],
        }
    )


def _toy_df_b() -> pd.DataFrame:
    """Sağ taraf: 18 satır (id 2–19), 3 kolon, value 1.0 offset."""
    return pd.DataFrame(
        {
            "id": list(range(2, 20)),
            "value": np.arange(2, 20, dtype=float) + 1.0,
            "label": ["a" if i % 2 == 0 else "b" for i in range(2, 20)],
        }
    )


# ---------------------------------------------------------------------------
# 1. profile_columns_wrapped — DataFrame → Dict[col, ColumnStats]
# ---------------------------------------------------------------------------


def test_profile_columns_real():
    """profile_columns: tüm kolonlar için null_rate, dtype, n_unique çıkarır."""
    df = _toy_df_a()
    content, artifact = _invoke_wrapper(profile_columns_wrapped, df=df)
    assert "ok" in content
    result = artifact["result"]
    assert "id" in result and "value" in result and "label" in result
    assert result["id"].n == 20
    assert result["value"].null_rate == 0.0


# ---------------------------------------------------------------------------
# 2. numeric_shift_wrapped — pd.Series → mean/std/null_rate shift
# ---------------------------------------------------------------------------


def test_numeric_shift_real():
    """numeric_shift: iki Series arasında mean/std/null_rate delta."""
    a = pd.Series(np.arange(20, dtype=float))
    b = pd.Series(np.arange(20, dtype=float) + 1.0)
    content, artifact = _invoke_wrapper(
        numeric_shift_wrapped,
        left=a,
        right=b,
    )
    assert "ok" in content
    result = artifact["result"]
    assert "mean_shift" in result
    assert abs(result["mean_shift"] - 1.0) < 0.01


# ---------------------------------------------------------------------------
# 3. schema_delta_wrapped — DataFrame → {added, removed, common}
# ---------------------------------------------------------------------------


def test_schema_delta_real():
    """schema_delta: iki DataFrame kolon kümelerini karşılaştırır."""
    left = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    right = pd.DataFrame({"a": [1, 2], "c": [5, 6]})
    content, artifact = _invoke_wrapper(
        schema_delta_wrapped,
        left=left,
        right=right,
    )
    assert "ok" in content
    added, removed, common = artifact["result"]
    assert "b" in removed
    assert "c" in added
    assert "a" in common


# ---------------------------------------------------------------------------
# 4. key_set_diff_wrapped — DataFrame, key='id' → added/removed
# ---------------------------------------------------------------------------


def test_key_set_diff_real():
    """key_set_diff: 2–19 vs 0–19 → 0,1 added; (boş) removed."""
    left = _toy_df_a()
    right = _toy_df_b()
    content, artifact = _invoke_wrapper(
        key_set_diff_wrapped,
        left=left,
        right=right,
        key="id",
    )
    assert "ok" in content
    added_keys, removed_keys = artifact["result"]
    assert 0 in added_keys and 1 in added_keys
    assert len(removed_keys) == 0


# ---------------------------------------------------------------------------
# 5. diff_summary_wrapped — DataFrame → DiffSummary dataclass
# ---------------------------------------------------------------------------


def test_diff_summary_real():
    """diff_summary: rows_added/removed, columns ekle/sil, drift_columns."""
    left = _toy_df_a()
    right = _toy_df_b()
    content, artifact = _invoke_wrapper(
        diff_summary_wrapped,
        left=left,
        right=right,
    )
    assert "ok" in content
    result = artifact["result"]
    assert result.rows_left == 20
    assert result.rows_right == 18


# ---------------------------------------------------------------------------
# 6. diff_payload_wrapped — DataFrame → UI-ready JSON payload
# ---------------------------------------------------------------------------


def test_diff_payload_real():
    """diff_payload: UI-ready structured diff (rows, cols, drift)."""
    left = _toy_df_a()
    right = _toy_df_b()
    content, artifact = _invoke_wrapper(
        diff_payload_wrapped,
        left=left,
        right=right,
    )
    assert "ok" in content
    result = artifact["result"]
    # diff_payload bir dict döner; anahtarlar versiyona göre değişebilir.
    assert isinstance(result, dict)
    assert len(result) > 0
    # En az bir 'rows' veya 'schema' related key olmalı
    keys_blob = str(list(result.keys())).lower()
    assert "row" in keys_blob or "schema" in keys_blob or "column" in keys_blob
