"""Tests for ``ai_data_science_team.tools.sheets`` (H5 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.sheets as h5


def _cfg(**kw):
    p = {"credentials_path": "/sa.json"}
    p.update(kw)
    return h5.ConnectorConfig(name="sheets", kind="sheets", params=p)


class TestBuild:
    def test_build(self):
        c = h5.build_sheets_connector(_cfg())
        assert c.kind == "sheets"

    def test_missing_credentials(self):
        with pytest.raises(ValueError):
            h5.build_sheets_connector(
                h5.ConnectorConfig(name="x", kind="sheets", params={})
            )

    def test_unknown_auth(self):
        with pytest.raises(h5.ConnectorError):
            h5.build_sheets_connector(_cfg(auth="weird"))

    def test_oauth_without_token(self):
        with pytest.raises(h5.ConnectorError):
            h5.build_sheets_connector(_cfg(auth="oauth"))


class TestBehaviors:
    def test_check_connection(self):
        c = h5.build_sheets_connector(_cfg())
        d = c.check_connection()
        assert d["auth"] == "service_account"

    def test_list_sheets_default(self):
        c = h5.build_sheets_connector(_cfg())
        s = c.list_sheets("ss-1")
        assert s[0]["title"] == "Sheet1"

    def test_register_sheets(self):
        c = h5.build_sheets_connector(_cfg())
        c.register_sheets("ss-1", [{"title": "Custom", "index": 1}])
        assert c.list_sheets("ss-1")[0]["title"] == "Custom"

    def test_read_range_default(self):
        c = h5.build_sheets_connector(_cfg())
        rows = c.read_range("ss-1", "Sheet1!A1:B2")
        assert rows == [[0, 0], [0, 0]]

    def test_read_range_registered(self):
        c = h5.build_sheets_connector(_cfg())
        c.register_range("ss-1", "Sheet1!A1:B2", [[1, 2], [3, 4]])
        assert c.read_range("ss-1", "Sheet1!A1:B2") == [[1, 2], [3, 4]]

    def test_read_range_invalid(self):
        c = h5.build_sheets_connector(_cfg())
        with pytest.raises(h5.ConnectorError):
            c.read_range("ss-1", "A1")

    def test_write_range(self):
        c = h5.build_sheets_connector(_cfg())
        r = c.write_range("ss-1", "Sheet1!A1:B2", [[1, 2], [3, 4]])
        assert r["status"] == "ok"
        assert r["rows_written"] == 2

