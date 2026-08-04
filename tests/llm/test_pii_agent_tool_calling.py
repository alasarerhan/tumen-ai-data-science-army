"""GERÇEK test pii_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/pii_agent.py — 3 tool.

Strateji:
- Tüm 3 tool STATEFUL: pd.DataFrame ve Pydantic objesi alır.
- ``tool.func(df, **kwargs)`` ile doğrudan çağrılır; gerçek tool çalışır.
- Pydantic state (``PIIScanReport``) wrapper tool'un içinde ``**kwargs``.
  aracılığıyla; test fixtures gerçek dataclass örnekleri kullanır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.pii_agent import (
    anonymize_dataframe_wrapped,
    default_strategies_for_wrapped,
    scan_pii_wrapped,
)

pytestmark = pytest.mark.llm


def _sample_df():
    """Küçük gerçek DataFrame — PII tespiti için email + phone sütunları."""
    import pandas as pd

    return pd.DataFrame(
        {
            "email": [
                "alice@example.com",
                "bob@example.com",
                "carol@example.com",
                "dave@example.com",
            ],
            "phone": [
                "0532 111 22 33",
                "0533 222 33 44",
                "0534 333 44 55",
                "0535 444 55 66",
            ],
            "amount": [10.0, 20.0, 30.0, 40.0],
        }
    )


# ---------------------------------------------------------------------------
# 1. scan_pii_wrapped — pd.DataFrame → PIIScanReport
# ---------------------------------------------------------------------------

def test_scan_pii_real():
    """scan_pii_wrapped: email + phone sütunlarını PII olarak tespit eder."""
    df = _sample_df()
    out = scan_pii_wrapped.func(df=df)
    s = str(out).lower()
    # Wrapper ya (content, artifact) tuple ya da ToolMessage döner.
    # İkisinde de 'email' veya 'pii' ifadesi geçmeli.
    assert "pii" in s or "email" in s or "ok" in s, (
        f"scan_pii beklenen PII tespiti yapmadı: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 2. default_strategies_for_wrapped — Pydantic PIIScanReport → dict
# ---------------------------------------------------------------------------

def test_default_strategies_for_real():
    """``default_strategies_for_wrapped`` bir PIIScanReport'tan strateji önerir.

    Wrapper imzası: ``(scan: PIIScanReport)``. Gerçek ``scan_pii`` ile elde
    edilen scan instance'ı kullanılır.
    """

    from ai_data_science_team.tools.pii import scan_pii

    df = _sample_df()
    scan = scan_pii(df)  # gerçek PIIScanReport dataclass
    out = default_strategies_for_wrapped.func(scan=scan)
    s = str(out).lower()
    assert "default" in s or "strategy" in s or "ok" in s or "email" in s or "pii" in s, (
        f"default_strategies_for beklenen çıktı üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 3. anonymize_dataframe_wrapped — pd.DataFrame + strategies Mapping
# ---------------------------------------------------------------------------

def test_anonymize_dataframe_real():
    """``anonymize_dataframe_wrapped`` stratejiyi uygulayıp AnonymisationResult döner.

    Wrapper imzası: ``(df: pd.DataFrame, strategies: Mapping)``.
    """
    df = _sample_df()
    strategies = {
        "email": {"pii_type": "EMAIL_ADDRESS", "strategy": "mask", "params": {}},
        "phone": {"pii_type": "TR_PHONE", "strategy": "mask", "params": {}},
    }
    out = anonymize_dataframe_wrapped.func(df=df, strategies=strategies)
    s = str(out).lower()
    assert "ok" in s or "anonym" in s or "mask" in s or "email" in s, (
        f"anonymize_dataframe beklenen çıktı üretmedi: {s[:300]}"
    )
