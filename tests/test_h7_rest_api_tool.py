"""Tests for ``ai_data_science_team.tools.h7_rest_api`` (H7 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.h7_rest_api as h7


def _cfg(**kw):
    p = {"base_url": "https://api.x"}
    p.update(kw)
    return h7.ConnectorConfig(name="r", kind="rest", params=p)


class TestBuild:
    def test_none_auth(self):
        c = h7.build_rest_connector(_cfg())
        assert c.kind == "rest"

    def test_missing_base_url(self):
        with pytest.raises(ValueError):
            h7.build_rest_connector(
                h7.ConnectorConfig(name="x", kind="rest", params={})
            )

    def test_bearer_missing_token(self):
        with pytest.raises(ValueError):
            h7.build_rest_connector(_cfg(auth="bearer"))

    def test_basic_missing_password(self):
        with pytest.raises(ValueError):
            h7.build_rest_connector(_cfg(auth="basic", username="u"))

    def test_unknown_auth(self):
        with pytest.raises(h7.ConnectorError):
            h7.build_rest_connector(_cfg(auth="weird"))


class TestBehaviors:
    def test_check_connection(self):
        c = h7.build_rest_connector(_cfg())
        d = c.check_connection()
        assert d["auth"] == "none"
        assert d["base_url"] == "https://api.x"

    def test_probe_default(self):
        c = h7.build_rest_connector(_cfg())
        p = c.probe("/")
        assert p["status"] == "ok"

    def test_probe_registered(self):
        c = h7.build_rest_connector(_cfg())
        c.register_probe("/x", {"status": "vip", "size_bytes": 999})
        assert c.probe("/x")["status"] == "vip"

    def test_schema_default(self):
        c = h7.build_rest_connector(_cfg())
        cols = c.schema_infer()
        assert any(col["name"] == "id" for col in cols)

    def test_schema_registered(self):
        c = h7.build_rest_connector(_cfg())
        c.register_schema(
            "/users", [{"name": "u_id", "type": "int"},
                       {"name": "u_email", "type": "string"}],
        )
        cols = c.schema_infer("/users")
        assert cols[0]["name"] == "u_id"

    def test_paginate_default(self):
        c = h7.build_rest_connector(_cfg())
        rows = c.paginate("/items", page_size=5, max_pages=2)
        assert len(rows) == 10

    def test_paginate_registered(self):
        c = h7.build_rest_connector(_cfg())
        c.paginate  # ensure attribute is initialised
        # Use a fake registered cache by injecting a real one.
        if not hasattr(c, "_paginate_cache"):
            c._paginate_cache = {}
        c._paginate_cache["/x"] = [{"k": 1}, {"k": 2}]
        assert c.paginate("/x") == [{"k": 1}, {"k": 2}]

