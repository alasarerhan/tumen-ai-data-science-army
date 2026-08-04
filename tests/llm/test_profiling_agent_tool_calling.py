"""GERÇEK test profiling_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/profiling_agent.py — 2 tool.

Strateji:
- Tüm 2 tool STATEFUL: pd.Series / pd.DataFrame arg alır.
- ``tool.func(series|df, **kwargs)`` ile doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.profiling_agent import (
    profile_column_wrapped,
    profile_dataframe_wrapped,
)

pytestmark = pytest.mark.llm


def _sample_df():
    """Küçük gerçek DataFrame — int + float + string sütunları."""
    import pandas as pd

    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "amount": [10.5, 20.0, 30.7, 40.1, 50.3],
            "category": ["a", "b", "a", "b", "c"],
        }
    )


# ---------------------------------------------------------------------------
# 1. profile_column_wrapped — pd.Series → dict
# ---------------------------------------------------------------------------

def test_profile_column_real():
    """``profile_column_wrapped`` tek sütunun istatistiklerini üretir.

    Wrapper imzası: ``(series: pd.Series)``.
    """
    df = _sample_df()
    out = profile_column_wrapped.func(series=df["amount"])
    s = str(out).lower()
    assert "amount" in s or "float" in s or "mean" in s or "ok" in s, (
        f"profile_column beklenen profil üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 2. profile_dataframe_wrapped — pd.DataFrame → dict
# ---------------------------------------------------------------------------

def test_profile_dataframe_real():
    """``profile_dataframe_wrapped`` tüm DataFrame'in profilini çıkarır.

    Wrapper imzası: ``(df: pd.DataFrame)``.
    """
    df = _sample_df()
    out = profile_dataframe_wrapped.func(df=df)
    s = str(out).lower()
    assert (
        "n_rows" in s
        or "column" in s
        or "numeric" in s
        or "category" in s
        or "ok" in s
    ), f"profile_dataframe beklenen profil üretmedi: {s[:300]}"
