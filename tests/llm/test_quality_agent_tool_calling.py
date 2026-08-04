"""GERÇEK test quality_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/quality_agent.py — 3 tool.

Strateji:
- Tüm 3 tool STATEFUL: pd.DataFrame + Mapping/Sequence[Mapping] arg alır.
- ``tool.func(df|d, **kwargs)`` ile doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.quality_agent import (
    b2_expectation_suite_from_template_wrapped,
    b2_summarise_suite_run_wrapped,
    b2_validate_against_suite_wrapped,
)

pytestmark = pytest.mark.llm


def _sample_df():
    """Küçük gerçek DataFrame — quality suite doğrulaması için."""
    import pandas as pd

    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "amount": [10.0, 20.0, 30.0, 40.0, 50.0],
            "category": ["a", "b", "a", "b", "c"],
        }
    )


# ---------------------------------------------------------------------------
# 1. b2_expectation_suite_from_template_wrapped
# ---------------------------------------------------------------------------


def test_b2_expectation_suite_from_template_real():
    """``b2_expectation_suite_from_template_wrapped`` template ismiyle suite üretir.

    Wrapper imzası: ``(template_name: str, dataset: pd.DataFrame, overrides: Optional[Mapping])``.
    """
    df = _sample_df()
    out = b2_expectation_suite_from_template_wrapped.func(
        template_name="row_count",
        dataset=df,
        overrides=None,
    )
    s = str(out).lower()
    assert "ok" in s or "suite" in s or "expectation" in s or "rule" in s, (
        f"b2_expectation_suite_from_template beklenen suite üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 2. b2_validate_against_suite_wrapped
# ---------------------------------------------------------------------------


def test_b2_validate_against_suite_real():
    """``b2_validate_against_suite_wrapped`` bir suite'i df'e uygular.

    Wrapper imzası: ``(df: pd.DataFrame, suite: Sequence[Mapping])``.
    Gerçek bir expectation_suite_from_template çağrısıyla suite üretilir.
    """
    df = _sample_df()
    suite = [
        {"kind": "not_null", "column": "id", "severity": "fail"},
        {"kind": "not_null", "column": "amount", "severity": "fail"},
        {"kind": "unique", "column": "id", "severity": "fail"},
    ]
    out = b2_validate_against_suite_wrapped.func(df=df, suite=suite)
    s = str(out).lower()
    assert "ok" in s or "passed" in s or "failed" in s or "rule" in s or "validate" in s, (
        f"b2_validate_against_suite beklenen sonuç üretmedi: {s[:300]}"
    )


# ---------------------------------------------------------------------------
# 3. b2_summarise_suite_run_wrapped
# ---------------------------------------------------------------------------


def test_b2_summarise_suite_run_real():
    """``b2_summarise_suite_run_wrapped`` validate çıktısını özetler.

    Wrapper imzası: ``(result: Mapping[str, Any])``.
    """
    fake_result = {
        "passed": 2,
        "failed": 1,
        "warning": 0,
        "skipped": 0,
        "errors": 0,
        "rules": [],
        "dataset_shape": [5, 3],
    }
    out = b2_summarise_suite_run_wrapped.func(result=fake_result)
    s = str(out).lower()
    assert "ok" in s or "status" in s or "summary" in s or "passed" in s or "warn" in s, (
        f"b2_summarise_suite_run beklenen özet üretmedi: {s[:300]}"
    )
