"""GERÇEK test feature_store_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/feature_store_agent.py — 9 tool.

Strateji:
- PURE (model-driven): ``version_sort_key_wrapped`` ve ``check_consistency_wrapped``
  model tarafından çağrılır.
- STATEFUL: ``register_feature``, ``search_features``, ``latest_version``,
  ``attach_lineage``, ``catalog_payload`` için gerçek ``FeatureStore``;
  ``probe_freshness``, ``bulk_probe_freshness`` için gerçek
  ``FreshnessRecord`` yaratılır ve **underlying tool** doğrudan çağrılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import time

import pytest

from ai_data_science_team.agents.feature_store_agent import (
    check_consistency_wrapped,
    version_sort_key_wrapped,
)
from ai_data_science_team.tools.feature_store import (
    FeatureStore,
    FreshnessRecord,
    attach_lineage,
    bulk_probe_freshness,
    catalog_payload,
    latest_version,
    probe_freshness,
    register_feature,
    search_features,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# 1. PURE: model-driven tool'lar
# ---------------------------------------------------------------------------

def test_version_sort_key_real(llm_or_skip, llm_model):
    tool = version_sort_key_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "version_sort_key_wrapped tool'unu TEK çağrı ile çağır; "
            "version='v2.10.3' ver.",
        ),
        tool.name,
    )


def test_check_consistency_real(llm_or_skip, llm_model):
    tool = check_consistency_wrapped
    _content, _ = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "check_consistency_wrapped tool'unu TEK çağrı ile çağır; "
            "parametresiz çağır.",
        ),
        tool.name,
    )


# ---------------------------------------------------------------------------
# 2. STATEFUL: FeatureStore / FreshnessRecord
# ---------------------------------------------------------------------------

def _fresh_store() -> FeatureStore:
    return FeatureStore()


def _seed_store() -> FeatureStore:
    """Test senaryosu: 2 feature kayıtlı store."""
    store = _fresh_store()
    register_feature(
        store,
        name="user_age",
        dtype="int",
        transform="age_at_event",
        owner="alice",
        tags=["user"],
    )
    register_feature(
        store,
        name="user_country",
        dtype="string",
        transform="country_code",
        owner="bob",
        tags=["user", "geo"],
    )
    return store


def test_register_feature_real():
    """register_feature: FeatureStore'a FeatureDefinition ekler."""
    store = _fresh_store()
    d = register_feature(
        store,
        name="session_dur",
        dtype="float",
        transform="session_duration_s",
        owner="alice",
    )
    assert d.name == "session_dur"
    assert len(store.definitions) == 1


def test_search_features_real():
    """search_features: query/tag/owner filtreleri."""
    store = _seed_store()
    out = search_features(store, query="user")
    assert len(out) >= 2
    out_tag = search_features(store, tag="geo")
    assert len(out_tag) == 1
    assert out_tag[0].name == "user_country"
    out_owner = search_features(store, owner="alice")
    assert len(out_owner) == 1
    assert out_owner[0].owner == "alice"


def test_latest_version_real():
    """latest_version: aynı name'in en yüksek version'ını döner."""
    store = _fresh_store()
    register_feature(
        store, name="score", dtype="float", transform="x",
        owner="a", version="1.0.0",
    )
    register_feature(
        store, name="score", dtype="float", transform="x",
        owner="a", version="1.2.0",
    )
    register_feature(
        store, name="score", dtype="float", transform="x",
        owner="a", version="1.10.0",
    )
    latest = latest_version(store, name="score")
    assert latest is not None
    assert latest.version == "1.10.0"
    assert latest_version(store, name="missing") is None


def test_probe_freshness_real():
    """probe_freshness: yaş + staleness bayrağı."""
    rec = FreshnessRecord(
        feature_id="f1",
        last_updated_at=time.time() - 100.0,
        freshness_sla_seconds=60.0,
    )
    report = probe_freshness(rec)
    assert report.feature_id == "f1"
    assert report.is_stale is True
    assert report.age_seconds >= 100.0


def test_bulk_probe_freshness_real():
    """bulk_probe_freshness: birden çok FreshnessRecord için FreshnessReport listesi."""
    records = [
        FreshnessRecord("f1", last_updated_at=time.time() - 30.0, freshness_sla_seconds=60.0),
        FreshnessRecord("f2", last_updated_at=time.time() - 200.0, freshness_sla_seconds=60.0),
    ]
    reports = bulk_probe_freshness(records)
    assert len(reports) == 2
    assert reports[0].is_stale is False
    assert reports[1].is_stale is True


def test_attach_lineage_real():
    """attach_lineage: feature'a lineage_node_id atar."""
    store = _seed_store()
    f = store.definitions[0]
    out = attach_lineage(
        store, feature_id=f.feature_id, lineage_node_id="node-42",
    )
    assert out.lineage_node_id == "node-42"


def test_catalog_payload_real():
    """catalog_payload: feature_id listesi → catalog dict."""
    store = _seed_store()
    ids = [d.feature_id for d in store.definitions]
    out = catalog_payload(store, ids)
    assert out["n"] == 2
    assert len(out["features"]) == 2
    unknown = catalog_payload(store, ["nonexistent"])
    assert unknown["n"] == 0
    assert unknown["features"] == []
