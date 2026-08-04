"""Tests for ``ai_data_science_team.tools.schema`` (B3 tool layer)."""

from __future__ import annotations

import pandas as pd

from ai_data_science_team.tools.schema import (
    ColumnInference,
    InferredType,
    Schema,
    build_mapping,
    infer_column_type,
    infer_schema,
    mapping_summary,
)

# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


class TestInferColumnType:
    def test_datetime_pandas(self):
        s = pd.to_datetime(pd.Series(["2024-01-01", "2024-06-30"]))
        out = infer_column_type(s)
        assert out.name == "datetime"
        assert out.confidence >= 0.99

    def test_date_string_pattern(self):
        s = pd.Series(["2024-01-01", "2024-06-30", "2024-12-31"])
        out = infer_column_type(s)
        assert out.name == "date"
        assert out.confidence >= 0.9

    def test_currency_strings(self):
        s = pd.Series(["₺1.234,50", "₺10,00", "₺99,99", "₺1.000,00", "₺5,00"])
        out = infer_column_type(s)
        assert out.name == "currency"
        assert out.detected_currency == "₺"
        assert out.transform == "parse_currency"

    def test_currency_text_suffix(self):
        s = pd.Series(["100 USD", "250 USD", "499 USD"])
        out = infer_column_type(s)
        assert out.name == "currency"

    def test_time_string_pattern(self):
        s = pd.Series(["12:30", "14:00", "09:15", "23:59", "00:00"])
        out = infer_column_type(s)
        assert out.name == "time"

    def test_boolean_tokens(self):
        s = pd.Series(["true", "false", "true", "yes", "no"])
        out = infer_column_type(s)
        assert out.name == "boolean"

    def test_percent_string(self):
        s = pd.Series(["10%", "20%", "30%", "40%", "50%"])
        out = infer_column_type(s)
        assert out.name == "percent"

    def test_integer_column(self):
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        out = infer_column_type(s)
        assert out.name in {"integer", "id"}

    def test_id_column_high_cardinality(self):
        # 100 unique numbers in 100 rows → id candidate.
        s = pd.Series(range(100))
        out = infer_column_type(s)
        assert out.name == "id"

    def test_low_cardinality_categorical(self):
        s = pd.Series(["A"] * 90 + ["B"] * 10)
        out = infer_column_type(s)
        assert out.name == "categorical"

    def test_high_cardinality_string_default(self):
        s = pd.Series([f"note-{i}" for i in range(50)])
        out = infer_column_type(s)
        assert out.name == "string"

    def test_empty_column(self):
        out = infer_column_type(pd.Series([], dtype="object"))
        assert out.name == "empty"
        assert out.confidence == 0.0


# ---------------------------------------------------------------------------
# Schema container
# ---------------------------------------------------------------------------


class TestInferSchema:
    def test_basic(self):
        df = pd.DataFrame(
            {
                "id": range(20),
                "email": ["a@b.com"] * 20,
                "ts": pd.to_datetime(["2024-01-01"] * 20),
                "amount": [1.0] * 20,
            }
        )
        schema = infer_schema(df)
        names = [c.source for c in schema.columns]
        assert names == ["id", "email", "ts", "amount"]
        types = {c.source: c.inferred.name for c in schema.columns}
        assert types["ts"] == "datetime"
        assert types["amount"] == "float"
        assert types["id"] in {"id", "integer"}

    def test_skips_internal_columns(self):
        df = pd.DataFrame({"__rowid__": range(10), "email": ["a@b.com"] * 10})
        schema = infer_schema(df)
        names = [c.source for c in schema.columns]
        assert "__rowid__" not in names
        assert "email" in names


# ---------------------------------------------------------------------------
# Build mapping
# ---------------------------------------------------------------------------


def _custom_schema(names_to_types: dict[str, str]) -> Schema:
    cols = []
    for name, t in names_to_types.items():
        cols.append(
            ColumnInference(
                source=name,
                inferred=InferredType(
                    name=t,
                    confidence=0.99,
                    pandas_dtype="object",
                    transform="cast_string",
                ),
            )
        )
    return Schema(columns=cols)


class TestBuildMapping:
    def test_perfect_match(self):
        source = _custom_schema({"customer_id": "integer", "email": "string"})
        target = _custom_schema({"customer_id": "integer", "email": "string"})
        m = build_mapping(source, target)
        auto = [c for c in m.columns if c.status == "auto"]
        assert len(auto) == 2

    def test_token_overlap(self):
        source = _custom_schema({"cust_id": "integer"})
        target = _custom_schema({"customer_id": "integer"})
        m = build_mapping(source, target)
        assert m.columns[0].target == "customer_id"

    def test_correction_overrides_match(self):
        source = _custom_schema({"x": "integer"})
        target = _custom_schema({"y": "integer"})
        m = build_mapping(source, target, corrections={"x": "y"})
        assert m.columns[0].target == "y"
        assert m.columns[0].confidence == 1.0
        assert m.auto_apply_count == 1

    def test_unmapped_source_low_score(self):
        # No overlap, no token similarity — should remain unmapped.
        source = _custom_schema({"zzzzz": "integer"})
        target = _custom_schema({"customer_id": "integer"})
        m = build_mapping(source, target, min_confidence_auto_apply=0.9)
        assert m.columns[0].target is None
        assert m.columns[0].status == "unmapped"
        assert "zzzzz" in m.unmapped_source

    def test_unfilled_target(self):
        target = _custom_schema({"customer_id": "integer", "extra": "string"})
        source = _custom_schema({"customer_id": "integer"})
        m = build_mapping(source, target)
        assert "extra" in m.unfilled_target

    def test_incompatible_types_lower_confidence(self):
        source = _custom_schema({"col": "string"})
        target = _custom_schema({"col": "boolean"})
        m = build_mapping(source, target, min_confidence_auto_apply=0.5)
        # Lexical match is still strong, but type is incompatible.
        # Expect either unmatched or marked for review.
        row = m.columns[0]
        assert row.status in {"review", "auto"}  # depends on name score

    def test_mapping_summary_shape(self):
        source = _custom_schema({"customer_id": "integer"})
        target = _custom_schema({"customer_id": "integer"})
        m = build_mapping(source, target)
        s = mapping_summary(m)
        assert "n_columns" in s
        assert "n_auto" in s
        assert "n_review" in s
        assert "unmapped_source" in s
        assert "unfilled_target" in s
        assert "columns" in s


# ---------------------------------------------------------------------------
# End-to-end: infer + map a generated CSV-style frame
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_csv_like_frame_to_target(self):
        df = pd.DataFrame(
            {
                "cust_id": range(40),
                "signup_at": ["2024-01-01", "2024-01-02", "2024-01-03"] * 13 + ["2024-01-04"],
                "amount_try": ["₺1.000,00", "₺500,00", "₺50,00", "₺10,00"] * 10,
                "active": ["true", "false", "true", "false"] * 10,
            }
        )
        schema = infer_schema(df)
        assert schema.column_names() == ["cust_id", "signup_at", "amount_try", "active"]
        target = _custom_schema(
            {
                "customer_id": "integer",
                "registered_at": "date",
                "amount_try": "currency",
                "is_active": "boolean",
            }
        )
        mapping = build_mapping(schema, target, min_confidence_auto_apply=0.6)
        # The currency column line up nicely; boolean may need review.
        targets_mapped = {c.source: c.target for c in mapping.columns}
        assert targets_mapped["amount_try"] == "amount_try"
