"""Tests for ``ai_data_science_team.tools.h6_object_storage`` (H6 tool layer)."""

from __future__ import annotations

import pytest

import ai_data_science_team.tools.h6_object_storage as h6


def _cfg(**kw):
    p = {"bucket": "bk", "provider": "s3"}
    p.update(kw)
    return h6.ConnectorConfig(name="obj", kind="object_storage", params=p)


class TestBuild:
    def test_s3(self):
        c = h6.build_object_storage_connector(_cfg())
        assert c.provider == "s3"

    def test_gcs(self):
        c = h6.build_object_storage_connector(_cfg(provider="gcs"))
        assert c.provider == "gcs"

    def test_missing_bucket(self):
        with pytest.raises(ValueError):
            h6.build_object_storage_connector(
                h6.ConnectorConfig(name="x", kind="object_storage",
                                    params={"provider": "s3"})
            )

    def test_unknown_provider(self):
        with pytest.raises(h6.ConnectorError):
            h6.build_object_storage_connector(_cfg(provider="azure"))


class TestBehaviors:
    def test_check_connection(self):
        c = h6.build_object_storage_connector(_cfg())
        d = c.check_connection()
        assert d["provider"] == "s3"
        assert d["bucket"] == "bk"

    def test_list_default(self):
        c = h6.build_object_storage_connector(_cfg())
        keys = [o["key"] for o in c.list_objects()]
        assert keys[0].startswith("data/")

    def test_list_registered(self):
        c = h6.build_object_storage_connector(_cfg())
        c.register_objects([
            {"key": "logs/2026-01.csv", "size": 100},
            {"key": "logs/2026-02.csv", "size": 200},
            {"key": "models/v1.bin", "size": 1_000_000},
        ])
        keys = [o["key"] for o in c.list_objects(prefix="logs/")]
        assert keys == ["logs/2026-01.csv", "logs/2026-02.csv"]

    def test_head_object(self):
        c = h6.build_object_storage_connector(_cfg())
        c.register_objects([{"key": "k1", "size": 42}])
        assert c.head_object("k1")["size"] == 42

    def test_head_object_missing(self):
        c = h6.build_object_storage_connector(_cfg())
        with pytest.raises(h6.ConnectorError):
            c.head_object("nope")

    def test_write_and_read(self):
        c = h6.build_object_storage_connector(_cfg())
        r = c.write_object("k1", b"hello")
        assert r["size"] == 5
        assert c.read_object("k1") == b"hello"

    def test_read_placeholder(self):
        c = h6.build_object_storage_connector(_cfg())
        # Not registered → deterministic placeholder.
        out = c.read_object("missing")
        assert out.startswith(b"placeholder-for-")

    def test_signed_url(self):
        c = h6.build_object_storage_connector(_cfg())
        u = c.signed_url("k1")
        assert "bk" in u
        assert "k1" in u


class TestRegistry:
    def test_present(self):
        for x in (
            "h6_object_storage_check_connection",
            "h6_object_storage_list",
            "h6_object_storage_read",
            "h6_object_storage_write",
            "h6_object_storage_signed_url",
            "h6_object_storage_head",
        ):
            assert x in h6.H6_OBJECT_STORAGE_TOOL_NAMES
