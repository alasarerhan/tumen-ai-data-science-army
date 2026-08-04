"""GERÇEK model-driven feature_store_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.feature_store_agent import (
    attach_lineage_wrapped,
    bulk_probe_freshness_wrapped,
    catalog_payload_wrapped,
    check_consistency_wrapped,
    latest_version_wrapped,
    probe_freshness_wrapped,
    register_feature_wrapped,
    search_features_wrapped,
    version_sort_key_wrapped,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def test_version_sort_key_real(llm_or_skip, llm_model):
    tool = version_sort_key_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "version_sort_key_wrapped tool'unu TEK çağrı ile çağır; version='v2.10.3' ver.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_check_consistency_real(llm_or_skip, llm_model):
    tool = check_consistency_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "check_consistency_wrapped tool'unu TEK çağrı ile çağır; parametresiz çağır.",
        ),
        tool.name,
    )
    assert content
    assert artifact is not None

def test_register_feature_stateful_skipped():
    assert hasattr(register_feature_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_search_features_stateful_skipped():
    assert hasattr(search_features_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_latest_version_stateful_skipped():
    assert hasattr(latest_version_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_probe_freshness_stateful_skipped():
    assert hasattr(probe_freshness_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_bulk_probe_freshness_stateful_skipped():
    assert hasattr(bulk_probe_freshness_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_attach_lineage_stateful_skipped():
    assert hasattr(attach_lineage_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")

def test_catalog_payload_stateful_skipped():
    assert hasattr(catalog_payload_wrapped, "func")
    pytest.skip("Nesne/store/state bağımlılığı olan tool; API entegrasyon testi gerekir")
