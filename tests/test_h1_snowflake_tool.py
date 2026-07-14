"""Tests for ``ai_data_science_team.tools.h1_snowflake`` (H1 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.h1_snowflake as h1


def _cfg(**kw):
    params = {"account": "x", "user": "u", "warehouse": "wh", "password": "p"}
    params.update(kw)
    return h1.ConnectorConfig(name="main", kind="snowflake", params=params)


class TestConnectorConfig:
    def test_get_default(self):
        c = _cfg()
        assert c.get("missing") is None
        assert c.get("missing", 5) == 5

    def test_require_raises(self):
        c = _cfg()
        with pytest.raises(ValueError):
            c.require("account_other")


class TestSnowflakeConnector:
    def test_build(self):
        c = h1.build_snowflake_connector(_cfg())
        assert c.kind == "snowflake"
        assert c.config.require("account") == "x"

    def test_missing_account(self):
        with pytest.raises(ValueError):
            h1.build_snowflake_connector(
                h1.ConnectorConfig(
                    name="x", kind="snowflake",
                    params={"user": "u", "password": "p"},
                )
            )

    def test_unknown_auth(self):
        with pytest.raises(h1.ConnectorError):
            h1.build_snowflake_connector(_cfg(auth="weird"))

    def test_sso_without_token(self):
        with pytest.raises(h1.ConnectorError):
            h1.build_snowflake_connector(_cfg(auth="sso"))

    def test_check_connection(self):
        c = h1.build_snowflake_connector(_cfg())
        d = c.check_connection()
        assert d["status"] == "ok"
        assert d["warehouse"] == "wh"
        assert d["auth"] == "keypair"

    def test_sample_query_select(self):
        c = h1.build_snowflake_connector(_cfg())
        rows = c.sample_query("SELECT 2 + 2")
        assert rows[0]["select_1"] == 1
        assert rows[0]["warehouse"] == "wh"

    def test_sample_query_rejects_non_select(self):
        c = h1.build_snowflake_connector(_cfg())
        with pytest.raises(h1.ConnectorError):
            c.sample_query("DELETE FROM x")

    def test_schema_introspect_via_cache(self):
        c = h1.build_snowflake_connector(_cfg())
        c.register_schema(
            "t1",
            [
                {"name": "id", "type": "BIGINT"},
                {"name": "name", "type": "TEXT"},
            ],
        )
        cols = c.schema_introspect("t1")
        assert cols[0]["name"] == "id"
        assert cols[1]["type"] == "TEXT"

    def test_schema_unknown_raises(self):
        c = h1.build_snowflake_connector(_cfg())
        with pytest.raises(h1.ConnectorError):
            c.schema_introspect("nope")

    def test_pushdown_query_plan(self):
        c = h1.build_snowflake_connector(_cfg())
        d = c.pushdown_query_plan("SELECT * FROM t")
        assert d["pushdown_eligible"] is True
        d2 = c.pushdown_query_plan("DELETE FROM t")
        assert d2["pushdown_eligible"] is False

