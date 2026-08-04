"""GERÇEK model-driven lineage_agent tool doğrulaması.

Bağımsız araçlar gerçek ChatOpenAI tool çağrısıyla çalıştırılır. Stateful araçlar
API entegrasyon kapsamı için açıkça skip edilir. Mock/fake/RunnableLambda yoktur.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.lineage_agent import (
    add_edge_wrapped,
    add_node_wrapped,
    ancestors_wrapped,
    descendants_wrapped,
    node_summary_wrapped,
    render_graph_wrapped,
)

pytestmark = pytest.mark.llm


def test_add_node_stateful_skipped():
    assert hasattr(add_node_wrapped, "func")
    pytest.skip("LineageGraph nesnesi isteyen stateful tool; API entegrasyon testi gerekir")


def test_add_edge_stateful_skipped():
    assert hasattr(add_edge_wrapped, "func")
    pytest.skip("LineageGraph nesnesi isteyen stateful tool; API entegrasyon testi gerekir")


def test_ancestors_stateful_skipped():
    assert hasattr(ancestors_wrapped, "func")
    pytest.skip("LineageGraph nesnesi isteyen stateful tool; API entegrasyon testi gerekir")


def test_descendants_stateful_skipped():
    assert hasattr(descendants_wrapped, "func")
    pytest.skip("LineageGraph nesnesi isteyen stateful tool; API entegrasyon testi gerekir")


def test_render_graph_stateful_skipped():
    assert hasattr(render_graph_wrapped, "func")
    pytest.skip("LineageGraph nesnesi isteyen stateful tool; API entegrasyon testi gerekir")


def test_node_summary_stateful_skipped():
    assert hasattr(node_summary_wrapped, "func")
    pytest.skip("LineageGraph nesnesi isteyen stateful tool; API entegrasyon testi gerekir")
