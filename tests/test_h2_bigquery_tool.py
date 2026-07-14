"""Tests for ``ai_data_science_team.tools.h2_bigquery`` (H2 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.h2_bigquery as h2


def _cfg(**kw):
    p = {"project": "my-p", "dataset": "ds1", "credentials_path": "/sa.json"}
    p.update(kw)
    return h2.ConnectorConfig(name="bq", kind="bigquery", params=p)


class TestBuild:
    def test_build(self):
        c = h2.build_bigquery_connector(_cfg())
        assert c.kind == "bigquery"

    def test_missing_project(self):
        with pytest.raises(ValueError):
            h2.build_bigquery_connector(
                h2.ConnectorConfig(
                    name="x", kind="bigquery",
                    params={"dataset": "d", "credentials_path": "/p"},
                )
            )

    def test_unknown_auth(self):
        with pytest.raises(h2.ConnectorError):
            h2.build_bigquery_connector(_cfg(auth="weird"))

    def test_oauth_without_token(self):
        with pytest.raises(h2.ConnectorError):
            h2.build_bigquery_connector(_cfg(auth="oauth"))


class TestBehaviors:
    def test_check_connection(self):
        c = h2.build_bigquery_connector(_cfg())
        d = c.check_connection()
        assert d["status"] == "ok"
        assert d["project"] == "my-p"

    def test_sample_query_select(self):
        c = h2.build_bigquery_connector(_cfg())
        rows = c.sample_query("SELECT 1")
        assert rows[0]["project"] == "my-p"

    def test_sample_query_rejects_non_select(self):
        c = h2.build_bigquery_connector(_cfg())
        with pytest.raises(h2.ConnectorError):
            c.sample_query("DROP TABLE x")

    def test_schema_introspect_via_cache(self):
        c = h2.build_bigquery_connector(_cfg())
        c.register_schema(
            "t1",
            [{"name": "x", "type": "INT64"}, {"name": "y", "type": "STRING"}],
        )
        cols = c.schema_introspect("t1")
        assert cols[0]["type"] == "INT64"

    def test_schema_unknown_raises(self):
        c = h2.build_bigquery_connector(_cfg())
        with pytest.raises(h2.ConnectorError):
            c.schema_introspect("nope")

    def test_query_cost_estimate(self):
        c = h2.build_bigquery_connector(_cfg())
        e = c.query_cost_estimate("SELECT 1", bytes_processed=1024 ** 4)
        # 1 TB → $5.
        assert e["estimated_cost_usd"] == 5.0

