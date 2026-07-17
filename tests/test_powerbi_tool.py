"""Tests for ``ai_data_science_team.tools.powerbi`` (H4 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.powerbi as h4


def _cfg(**kw):
    p = {
        "tenant_id": "t", "client_id": "c", "client_secret": "s",
        "workspace_id": "ws-1",
    }
    p.update(kw)
    return h4.ConnectorConfig(name="pbi", kind="powerbi", params=p)


class TestBuild:
    def test_build(self):
        c = h4.build_powerbi_connector(_cfg())
        assert c.kind == "powerbi"

    def test_missing_tenant(self):
        with pytest.raises(ValueError):
            h4.build_powerbi_connector(
                h4.ConnectorConfig(
                    name="x", kind="powerbi",
                    params={"client_id": "c", "client_secret": "s",
                            "workspace_id": "ws"},
                )
            )

    def test_no_workspace(self):
        with pytest.raises(h4.ConnectorError):
            h4.build_powerbi_connector(
                h4.ConnectorConfig(
                    name="x", kind="powerbi",
                    params={"tenant_id": "t", "client_id": "c",
                            "client_secret": "s"},
                )
            )

    def test_workspace_name_alternative(self):
        c = h4.build_powerbi_connector(_cfg(workspace_id=None,
                                            workspace_name="Sales"))
        assert c.config.get("workspace_name") == "Sales"


class TestBehaviors:
    def test_check_connection(self):
        c = h4.build_powerbi_connector(_cfg())
        d = c.check_connection()
        assert d["tenant_id"] == "t"
        assert d["workspace_id"] == "ws-1"

    def test_list_workspaces_default(self):
        c = h4.build_powerbi_connector(_cfg())
        ws = c.list_workspaces()
        assert ws and ws[0]["name"] == "ws1"  # default workspace_name fallback

    def test_register_workspaces(self):
        c = h4.build_powerbi_connector(_cfg())
        c.register_workspaces([{"id": "w1", "name": "Foo"}])
        assert c.list_workspaces()[0]["id"] == "w1"

    def test_list_datasets(self):
        c = h4.build_powerbi_connector(_cfg())
        ds = c.list_datasets()
        assert ds[0]["workspace_id"] == "ws-1"

    def test_register_datasets(self):
        c = h4.build_powerbi_connector(_cfg())
        c.register_datasets([{"id": "d1", "name": "X", "workspace_id": "ws-1"}])
        assert c.list_datasets()[0]["name"] == "X"

    def test_refresh_dataset(self):
        c = h4.build_powerbi_connector(_cfg())
        r = c.refresh_dataset("ds-1")
        assert r["status"] == "queued"

    def test_sample_query_dax(self):
        c = h4.build_powerbi_connector(_cfg())
        rows = c.sample_query("EVALUATE ROW(\"k\", 1)")
        assert rows[0]["value"] == 1

    def test_sample_query_rejects_non_evaluate(self):
        c = h4.build_powerbi_connector(_cfg())
        with pytest.raises(h4.ConnectorError):
            c.sample_query("SELECT 1")

    def test_run_dax_alias(self):
        c = h4.build_powerbi_connector(_cfg())
        rows = c.run_dax("EVALUATE ROW(\"k\", 1)")
        assert rows[0]["value"] == 1

