"""Tests for D3 Feature Store tool."""
from __future__ import annotations

import pytest

import ai_data_science_team.tools.d3_feature_store as d3


@pytest.fixture
def store():
    return d3.FeatureStore()


@pytest.fixture
def populated_store(store):
    d3.register_feature(
        store, name="user_age", dtype="int",
        transform="raw_age", owner="alice",
        tags=["user", "demographic"], description="user age in years",
    )
    d3.register_feature(
        store, name="user_age", dtype="int",
        transform="raw_age_v2", owner="alice",
        tags=["user"], version="2.0.0",
    )
    d3.register_feature(
        store, name="txn_amount_30d", dtype="float",
        transform="rolling_sum", owner="bob",
        tags=["transaction"], description="sum of last 30d txns",
    )
    return store


class TestRegisterFeature:
    def test_returns_definition(self, store):
        d = d3.register_feature(
            store, name="x", dtype="float",
            transform="raw", owner="alice",
        )
        assert d.name == "x"
        assert d.dtype == "float"
        assert d.version == "1.0.0"
        assert d.tags == []
        assert d.lineage_node_id is None

    def test_invalid_dtype(self, store):
        with pytest.raises(ValueError):
            d3.register_feature(
                store, name="x", dtype="datetime",
                transform="raw", owner="alice",
            )

    def test_with_lineage(self, store):
        d = d3.register_feature(
            store, name="x", dtype="int",
            transform="raw", owner="alice",
            lineage_node_id="node-abc",
        )
        assert d.lineage_node_id == "node-abc"


class TestStoreAccessors:
    def test_by_id(self, populated_store):
        all_defs = populated_store.definitions
        d = populated_store.by_id(all_defs[0].feature_id)
        assert d is all_defs[0]

    def test_by_name(self, populated_store):
        rows = populated_store.by_name("user_age")
        assert len(rows) == 2

    def test_by_id_missing(self, store):
        assert store.by_id("nope") is None


class TestSearch:
    def test_query(self, populated_store):
        out = d3.search_features(populated_store, query="txn")
        assert len(out) == 1
        assert out[0].name == "txn_amount_30d"

    def test_query_in_description(self, populated_store):
        out = d3.search_features(populated_store, query="years")
        assert len(out) == 1
        assert out[0].name == "user_age"

    def test_filter_by_tag(self, populated_store):
        out = d3.search_features(populated_store, tag="transaction")
        assert len(out) == 1
        assert out[0].owner == "bob"

    def test_filter_by_owner(self, populated_store):
        out = d3.search_features(populated_store, owner="alice")
        assert len(out) == 2

    def test_filter_by_dtype(self, populated_store):
        out = d3.search_features(populated_store, dtype="float")
        assert len(out) == 1

    def test_combined_filters(self, populated_store):
        out = d3.search_features(
            populated_store, tag="user", owner="alice",
        )
        assert len(out) == 2

    def test_limit(self, populated_store):
        out = d3.search_features(populated_store, limit=1)
        assert len(out) == 1


class TestLatestVersion:
    def test_picks_highest(self, populated_store):
        latest = d3.latest_version(populated_store, "user_age")
        assert latest is not None
        assert latest.version == "2.0.0"

    def test_unknown_name(self, store):
        assert d3.latest_version(store, "nope") is None

    def test_three_part_version(self):
        s = d3.FeatureStore()
        d3.register_feature(
            s, name="x", dtype="int",
            transform="raw", owner="alice", version="1.2.3",
        )
        d3.register_feature(
            s, name="x", dtype="int",
            transform="raw", owner="alice", version="1.10.0",
        )
        latest = d3.latest_version(s, "x")
        assert latest.version == "1.10.0"


class TestConsistency:
    def test_consistent(self):
        r = d3.check_consistency(
            feature_id="f1",
            online_dtype="float", offline_dtype="float",
            online_value_sample=[1.0, 2.0, 3.0],
            offline_value_sample=[1.0, 2.0, 3.0],
        )
        assert r.consistent is True
        assert r.issues == []

    def test_dtype_mismatch(self):
        r = d3.check_consistency(
            feature_id="f1",
            online_dtype="float", offline_dtype="string",
            online_value_sample=["1.0", "2.0"],
            offline_value_sample=["1.0", "2.0"],
        )
        assert r.consistent is False
        assert r.dtypes_match is False
        assert any("dtype mismatch" in i for i in r.issues)

    def test_sample_mismatch(self):
        r = d3.check_consistency(
            feature_id="f1",
            online_dtype="float", offline_dtype="float",
            online_value_sample=[1.0, 2.0],
            offline_value_sample=[1.0, 2.5],
        )
        assert r.consistent is False
        assert r.samples_match is False

    def test_length_mismatch(self):
        r = d3.check_consistency(
            feature_id="f1",
            online_dtype="float", offline_dtype="float",
            online_value_sample=[1.0, 2.0],
            offline_value_sample=[1.0],
        )
        assert r.samples_match is False

    def test_online_dtype_none(self):
        r = d3.check_consistency(
            feature_id="f1",
            online_dtype=None, offline_dtype="float",
            online_value_sample=[],
            offline_value_sample=[],
        )
        assert r.dtypes_match is False


class TestFreshness:
    def test_fresh(self):
        rec = d3.FreshnessRecord(
            feature_id="f1",
            last_updated_at=1000.0,
            freshness_sla_seconds=300.0,
        )
        r = d3.probe_freshness(rec, now=1100.0)
        assert r.age_seconds == 100.0
        assert r.is_stale is False

    def test_stale(self):
        rec = d3.FreshnessRecord(
            feature_id="f1",
            last_updated_at=1000.0,
            freshness_sla_seconds=300.0,
        )
        r = d3.probe_freshness(rec, now=2000.0)
        assert r.is_stale is True

    def test_bulk(self):
        recs = [
            d3.FreshnessRecord(feature_id="a", last_updated_at=0,
                                freshness_sla_seconds=10),
            d3.FreshnessRecord(feature_id="b", last_updated_at=0,
                                freshness_sla_seconds=1000),
        ]
        reports = d3.bulk_probe_freshness(recs, now=50)
        assert reports[0].is_stale is True
        assert reports[1].is_stale is False


class TestLineageAttach:
    def test_attach(self, populated_store):
        d = populated_store.definitions[0]
        d3.attach_lineage(
            populated_store,
            feature_id=d.feature_id,
            lineage_node_id="lin-node-1",
        )
        assert d.lineage_node_id == "lin-node-1"

    def test_unknown_feature(self, store):
        with pytest.raises(KeyError):
            d3.attach_lineage(
                store, feature_id="nope", lineage_node_id="x",
            )


class TestCatalogPayload:
    def test_payload(self, populated_store):
        fids = [d.feature_id for d in populated_store.definitions[:2]]
        p = d3.catalog_payload(populated_store, fids)
        assert p["n"] == 2
        assert len(p["features"]) == 2
        assert all("name" in f for f in p["features"])

    def test_unknown_skipped(self, populated_store):
        p = d3.catalog_payload(populated_store, ["nope"])
        assert p["n"] == 0

