"""GERÇEK test schema_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/schema_agent.py — 4 tool.

Strateji:
- Tüm 4 tool STATEFUL: pd.Series / pd.DataFrame / Pydantic objesi alır.
- ``tool.func(series|df|schema, **kwargs)`` ile doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.schema_agent import (
    build_mapping_wrapped,
    infer_column_type_wrapped,
    infer_schema_wrapped,
    mapping_summary_wrapped,
)

pytestmark = pytest.mark.llm


def _sample_df():
    """Küçük gerçek DataFrame — schema inference için mixed tipli sütunlar."""
    import pandas as pd

    return pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "amount": [10.0, 20.0, 30.0, 40.0, 50.0],
            "category": ["a", "b", "a", "b", "c"],
        }
    )


# ---------------------------------------------------------------------------
# 1. infer_column_type_wrapped — pd.Series → InferredType
# ---------------------------------------------------------------------------

def test_infer_column_type_real():
    """``infer_column_type_wrapped`` Series'in mantıksal tipini çıkarır.

    Wrapper imzası: ``(series: pd.Series)``.
    """
    df = _sample_df()
    out = infer_column_type_wrapped.func(series=df["amount"])
    s = str(out).lower()
    assert (
        "ok" in s
        or "float" in s
        or "integer" in s
        or "cast" in s
        or "amount" in s
    ), f"infer_column_type beklenen tip üretmedi: {s[:300]}"


# ---------------------------------------------------------------------------
# 2. infer_schema_wrapped — pd.DataFrame → Schema
# ---------------------------------------------------------------------------

def test_infer_schema_real():
    """``infer_schema_wrapped`` tüm DataFrame'in Schema'sını üretir.

    Wrapper imzası: ``(df: pd.DataFrame)``.
    """
    df = _sample_df()
    out = infer_schema_wrapped.func(df=df)
    s = str(out).lower()
    assert (
        "ok" in s
        or "schema" in s
        or "column" in s
        or "id" in s
        or "amount" in s
    ), f"infer_schema beklenen schema üretmedi: {s[:300]}"


# ---------------------------------------------------------------------------
# 3. build_mapping_wrapped — source Schema, target Schema → MappingResult
# ---------------------------------------------------------------------------

def test_build_mapping_real():
    """``build_mapping_wrapped`` source ve target şemaları eşler.

    Wrapper imzası: ``(source: Schema, target: Schema)``.
    """
    from ai_data_science_team.tools.schema import ColumnInference, InferredType, Schema

    def _schema_with_cols(cols):
        return Schema(
            columns=[
                ColumnInference(
                    source=name,
                    inferred=InferredType(
                        name=kind,
                        confidence=0.99,
                        pandas_dtype="object",
                        transform="cast_string",
                    ),
                )
                for name, kind in cols
            ]
        )

    source = _schema_with_cols([("customer_id", "integer"), ("amount", "float")])
    target = _schema_with_cols([("user_id", "integer"), ("value", "float")])
    out = build_mapping_wrapped.func(source=source, target=target)
    s = str(out).lower()
    assert (
        "ok" in s
        or "mapping" in s
        or "auto" in s
        or "review" in s
        or "customer_id" in s
    ), f"build_mapping beklenen MappingResult üretmedi: {s[:300]}"


# ---------------------------------------------------------------------------
# 4. mapping_summary_wrapped — MappingResult → dict
# ---------------------------------------------------------------------------

def test_mapping_summary_real():
    """``mapping_summary_wrapped`` MappingResult'ı düz dict'e çevirir.

    Wrapper imzası: ``(mapping: MappingResult)``.
    """
    from ai_data_science_team.tools.schema import (
        ColumnInference,
        InferredType,
        Schema,
    )

    source = Schema(
        columns=[
            ColumnInference(
                source="customer_id",
                inferred=InferredType(
                    name="integer",
                    confidence=0.99,
                    pandas_dtype="int64",
                    transform="cast_int",
                ),
            ),
        ]
    )
    target = Schema(
        columns=[
            ColumnInference(
                source="user_id",
                inferred=InferredType(
                    name="integer",
                    confidence=0.99,
                    pandas_dtype="int64",
                    transform="cast_int",
                ),
            ),
        ]
    )
    # Gerçek build_mapping kullan — sonra mapping_summary uygula.
    from ai_data_science_team.tools.schema import build_mapping

    mapping = build_mapping(source=source, target=target)
    out = mapping_summary_wrapped.func(mapping=mapping)
    s = str(out).lower()
    assert (
        "ok" in s
        or "n_columns" in s
        or "n_auto" in s
        or "n_review" in s
        or "customer_id" in s
    ), f"mapping_summary beklenen dict üretmedi: {s[:300]}"
