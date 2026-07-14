"""Tests for ``ai_data_science_team.tools.h3_tableau`` (H3 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.h3_tableau as h3


def _cfg(**kw):
    p = {
        "server_url": "https://t.s",
        "site": "site1",
        "token_name": "t",
        "token_value": "v",
    }
    p.update(kw)
    return h3.ConnectorConfig(name="t", kind="tableau", params=p)


class TestBuild:
    def test_build(self):
        c = h3.build_tableau_connector(_cfg())
        assert c.kind == "tableau"

    def test_missing_server(self):
        with pytest.raises(ValueError):
            h3.build_tableau_connector(
                h3.ConnectorConfig(
                    name="x", kind="tableau",
                    params={"site": "s", "token_name": "n", "token_value": "v"},
                )
            )

    def test_unknown_auth(self):
        with pytest.raises(h3.ConnectorError):
            h3.build_tableau_connector(_cfg(auth="weird"))

    def test_user_pass_missing(self):
        with pytest.raises(ValueError):
            h3.build_tableau_connector(_cfg(auth="username_password"))


class TestBehaviors:
    def test_check_connection(self):
        c = h3.build_tableau_connector(_cfg())
        d = c.check_connection()
        assert d["server_url"] == "https://t.s"
        assert d["auth"] == "pat"

    def test_list_workbooks_default(self):
        c = h3.build_tableau_connector(_cfg())
        w = c.list_workbooks()
        assert len(w) >= 2

    def test_register_workbooks(self):
        c = h3.build_tableau_connector(_cfg())
        c.register_workbooks([{"id": "a", "name": "x", "project": "p"}])
        assert c.list_workbooks()[0]["id"] == "a"

    def test_sample_query_select(self):
        c = h3.build_tableau_connector(_cfg())
        rows = c.sample_query("SELECT * FROM t")
        assert rows[0]["ok"] == 1

    def test_sample_query_rejects_non_select(self):
        c = h3.build_tableau_connector(_cfg())
        with pytest.raises(h3.ConnectorError):
            c.sample_query("DROP TABLE x")

    def test_schema_introspect_via_cache(self):
        c = h3.build_tableau_connector(_cfg())
        c.register_schema("ds1", [{"name": "a", "type": "INTEGER"}])
        cols = c.schema_introspect("ds1")
        assert cols[0]["type"] == "INTEGER"

    def test_schema_unknown_raises(self):
        c = h3.build_tableau_connector(_cfg())
        with pytest.raises(h3.ConnectorError):
            c.schema_introspect("nope")

    def test_export_workbook_format(self):
        c = h3.build_tableau_connector(_cfg())
        r = c.export_workbook("wb-1", fmt="pdf")
        assert r["format"] == "pdf"
        with pytest.raises(h3.ConnectorError):
            c.export_workbook("wb-1", fmt="weird")

