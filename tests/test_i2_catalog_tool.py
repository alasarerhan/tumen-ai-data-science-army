"""Tests for ``ai_data_science_team.tools.i2_catalog`` (I2 tool layer)."""

from __future__ import annotations

import pandas as pd
import pytest

from ai_data_science_team.tools.i2_catalog import (
    DEFAULT_SYNONYMS,
    Catalog,
    add_pii_badges,
    add_source,
    add_table,
    add_term,
    attach_profile,
    bind_term_column,
    catalog_tree,
    lineage_for,
    make_catalog,
    record_lineage,
    resolve_data,
    search,
)


def _seed_catalog() -> "Catalog":
    cat = make_catalog()
    add_source(
        cat,
        name="snowflake.public",
        kind="snowflake",
        tables=[
            {
                "name": "customers",
                "columns": [
                    {"name": "id", "dtype": "int64"},
                    {"name": "email", "dtype": "object", "description": "Customer email address"},
                    {"name": "lifetime_value", "dtype": "float64"},
                ],
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "order_id", "dtype": "int64"},
                    {"name": "amount_try", "dtype": "object", "description": "Order amount in TL"},
                    {"name": "created_at", "dtype": "datetime64[ns]"},
                ],
            },
        ],
    )
    add_source(
        cat,
        name="warehouse.curated",
        kind="snowflake",
        tables=[
            {
                "name": "churn_label",
                "columns": [
                    {"name": "user_id", "dtype": "int64"},
                    {"name": "churned", "dtype": "int64"},
                    {"name": "churned_at", "dtype": "datetime64[ns]"},
                ],
            }
        ],
    )
    return cat


# ---------------------------------------------------------------------------
# add_source / add_table / catalog_tree
# ---------------------------------------------------------------------------


class TestAddSource:
    def test_basic(self):
        cat = make_catalog()
        src = add_source(
            cat,
            name="warehouse",
            kind="postgres",
            tables=[
                {
                    "name": "users",
                    "columns": [{"name": "uid"}],
                }
            ],
        )
        assert src.name == "warehouse"
        assert src.kind == "postgres"
        assert len(src.tables) == 1
        assert src.tables[0].column_names() == ["uid"]

    def test_add_table_appends(self):
        cat = make_catalog()
        add_source(cat, name="warehouse", kind="postgres")
        added = add_table(
            cat,
            "warehouse",
            "products",
            [{"name": "pid"}, {"name": "price"}],
            description="Product catalog",
        )
        assert added is not None
        assert added.column_names() == ["pid", "price"]

    def test_add_table_missing_source(self):
        cat = make_catalog()
        out = add_table(cat, "missing", "users", [{"name": "uid"}])
        assert out is None


class TestCatalogTree:
    def test_counts(self):
        cat = _seed_catalog()
        tree = catalog_tree(cat)
        assert tree["n_sources"] == 2
        assert tree["n_tables"] == 3
        # 3 + 3 + 3 = 9 columns
        assert tree["n_columns"] == 9

    def test_tree_includes_pii(self):
        cat = _seed_catalog()
        # Add a PII finding then re-check.
        cat.terms  # touch
        tree = catalog_tree(cat)
        assert "sources" in tree
        assert tree["sources"][0]["tables"][0]["columns"][0]["name"] == "id"


# ---------------------------------------------------------------------------
# attach_profile / add_pii_badges
# ---------------------------------------------------------------------------


class TestAttachProfile:
    def test_updates_existing_stats(self):
        cat = _seed_catalog()
        profile = {
            "columns": [
                {
                    "name": "email",
                    "dtype": "object",
                    "n_missing": 5,
                    "n_unique": 100,
                }
            ]
        }
        attach_profile(cat, "snowflake.public", profile)
        col = cat.find_source("snowflake.public").tables[0].get_column("email")
        assert col.stats["n_missing"] == 5
        assert col.stats["n_unique"] == 100

    def test_adds_new_column(self):
        cat = _seed_catalog()
        profile = {
            "columns": [
                {
                    "name": "extra_col",
                    "dtype": "object",
                    "n_missing": 0,
                }
            ]
        }
        attach_profile(cat, "snowflake.public", profile)
        cols = cat.find_source("snowflake.public").tables[0].column_names()
        assert "extra_col" in cols

    def test_missing_source_silently_skips(self):
        cat = make_catalog()
        attach_profile(cat, "missing", {"columns": []})  # no raise


class TestAddPIIBadges:
    def test_badges_persisted(self):
        cat = _seed_catalog()
        pii = {
            "findings": [
                {
                    "column": "email",
                    "pii_signal": "high",
                    "pii_kind": "email",
                    "match_ratio": 0.95,
                }
            ]
        }
        add_pii_badges(cat, "snowflake.public", pii)
        col = cat.find_source("snowflake.public").tables[0].get_column("email")
        assert col.pii["signal"] == "high"
        assert col.pii["kind"] == "email"

    def test_missing_source_silently_skips(self):
        cat = make_catalog()
        add_pii_badges(cat, "missing", {"findings": []})


# ---------------------------------------------------------------------------
# Terms + search + resolve_data
# ---------------------------------------------------------------------------


class TestTermsAndSearch:
    def test_churn_search(self):
        cat = _seed_catalog()
        # Adding churn synonym in catalog is automatic via DEFAULT_SYNONYMS.
        hits = search(cat, "churn", top_k=5)
        # The "churn_label" table has a "churned" column → strong match.
        targets = [(h.source, h.table, h.column) for h in hits]
        assert ("warehouse.curated", "churn_label", "churned") in targets

    def test_turkish_synonym_lookup(self):
        cat = _seed_catalog()
        # "müşteri kaybı" expands via DEFAULT_SYNONYMS to "churn".
        hits = search(cat, "müşteri kaybı", top_k=5)
        assert any(h.table == "churn_label" for h in hits)

    def test_ltv_match(self):
        cat = _seed_catalog()
        # ltv → "lifetime_value" column.
        hits = search(cat, "ltv", top_k=5)
        assert any(h.column == "lifetime_value" for h in hits)

    def test_revenue_match(self):
        cat = _seed_catalog()
        # "revenue" → "amount_try" via "income" synonym (description
        # "Order amount in TL" + synonym expansion).
        hits = search(cat, "revenue", top_k=5)
        assert any(h.column == "amount_try" for h in hits)

    def test_search_returns_top_k(self):
        cat = _seed_catalog()
        hits = search(cat, "x", top_k=2)
        assert len(hits) <= 2

    def test_zero_top_k_raises(self):
        cat = _seed_catalog()
        with pytest.raises(ValueError):
            search(cat, "x", top_k=0)

    def test_empty_query_returns_empty(self):
        cat = _seed_catalog()
        assert search(cat, "  ", top_k=5) == []

    def test_resolve_data_shape(self):
        cat = _seed_catalog()
        out = resolve_data(cat, "churn", top_k=3)
        assert isinstance(out, list)
        assert all("source" in d and "column" in d for d in out)

    def test_direct_term_binding_promotes(self):
        cat = _seed_catalog()
        add_term(cat, "ltv", synonyms=["lifetime value"])
        bind_term_column(
            cat,
            "ltv",
            source="snowflake.public",
            table="customers",
            column="lifetime_value",
            confidence=0.95,
        )
        hits = search(cat, "ltv", top_k=3)
        assert hits[0].score >= 0.95
        assert hits[0].column == "lifetime_value"

    def test_dedupes_repeated_columns(self):
        cat = _seed_catalog()
        hits = search(cat, "id", top_k=5)
        # No duplicate (source, table, column).
        seen = set()
        for h in hits:
            k = (h.source, h.table, h.column)
            assert k not in seen
            seen.add(k)

    def test_default_synonyms_populated(self):
        cat = make_catalog()
        assert "churn" in cat.synonym_table


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


class TestLineage:
    def test_record_and_query(self):
        cat = _seed_catalog()
        record_lineage(
            catalog=cat, pipeline_id="wf_1", source_name="snowflake.public", table="customers"
        )
        record_lineage(
            catalog=cat, pipeline_id="wf_2", source_name="snowflake.public", table="orders"
        )
        out = lineage_for(cat, "snowflake.public")
        assert len(out) == 2
        out_customers = lineage_for(cat, "snowflake.public", table="customers")
        assert len(out_customers) == 1
        assert out_customers[0]["pipeline_id"] == "wf_1"

    def test_lineage_for_missing_source(self):
        cat = _seed_catalog()
        assert lineage_for(cat, "does_not_exist") == []
