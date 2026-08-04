"""GERÇEK lineage_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/lineage_agent.py — 6 tool.

Strateji:
- TÜM tool'lar ``graph: LineageGraph`` arg alır (Pydantic JSON-serializable
  değil, runtime object). Model-driven harness'te çalışmazlar;
  tools/lineage.py doğrudan çağrılır. Gerçek LineageGraph instance test'te
  yaratılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.lineage import (
    LineageGraph,
    add_edge,
    add_node,
    ancestors,
    descendants,
    node_summary,
    render_graph,
)

pytestmark = pytest.mark.llm


def _seeded_graph() -> LineageGraph:
    """Test için taze, izole LineageGraph — 3 node + 2 edge (source→dataset→model).

    Zincir: src → ds → mdl.
    """
    g = LineageGraph()
    add_node(graph=g, kind="source", label="raw.csv", node_id="src")
    add_node(graph=g, kind="dataset", label="features.parquet", node_id="ds")
    add_node(graph=g, kind="model", label="xgb_v1", node_id="mdl")
    add_edge(graph=g, source="src", target="ds", relation="produces")
    add_edge(graph=g, source="ds", target="mdl", relation="trains")
    return g


# ---------------------------------------------------------------------------
# STATEFUL: tüm tool'lar LineageGraph arg alır → tools/lineage.py
# ---------------------------------------------------------------------------


def test_add_node_real():
    """add_node(graph, *, kind, label, ...) → LineageNode; graph.nodes büyür."""
    g = LineageGraph()
    n = add_node(graph=g, kind="source", label="raw.csv", node_id="n1")
    assert n is not None
    assert n.node_id == "n1"
    assert n.kind == "source"
    assert n.label == "raw.csv"
    assert len(g.nodes) == 1


def test_add_edge_real():
    """add_edge(graph, source, target, relation='produces') → LineageEdge."""
    g = _seeded_graph()
    assert len(g.edges) == 2


def test_ancestors_real():
    """ancestors(graph, node_id) → List[str] upstream node_id'leri BFS ile."""
    g = _seeded_graph()
    # mdl upstream: ds, src (BFS over incoming edges)
    ups = ancestors(graph=g, node_id="mdl")
    assert isinstance(ups, list)
    assert set(ups) == {"ds", "src"}
    # src upstream: []
    assert ancestors(graph=g, node_id="src") == []


def test_descendants_real():
    """descendants(graph, node_id) → List[str] downstream node_id'leri BFS ile."""
    g = _seeded_graph()
    # src downstream: ds, mdl
    downs = descendants(graph=g, node_id="src")
    assert isinstance(downs, list)
    assert set(downs) == {"ds", "mdl"}
    # mdl downstream: []
    assert descendants(graph=g, node_id="mdl") == []


def test_render_graph_real():
    """render_graph(graph, *, highlight_node=None, mode='full') → UI-ready dict."""
    g = _seeded_graph()
    out = render_graph(graph=g, mode="full")
    assert isinstance(out, dict)
    assert "nodes" in out and "edges" in out and "highlight" in out
    assert out["mode"] == "full"
    assert {n["id"] for n in out["nodes"]} == {"src", "ds", "mdl"}
    # impact mode + highlight_node → highlight list = [node, descendants...]
    out2 = render_graph(graph=g, highlight_node="ds", mode="impact")
    assert out2["mode"] == "impact"
    assert set(out2["highlight"]) == {"ds", "mdl"}


def test_node_summary_real():
    """node_summary(graph, node_id) → {node, ancestors, descendants} dict."""
    g = _seeded_graph()
    out = node_summary(graph=g, node_id="ds")
    assert isinstance(out, dict)
    assert "node" in out and "ancestors" in out and "descendants" in out
    assert out["node"]["id"] == "ds"
    assert out["node"]["kind"] == "dataset"
    assert set(out["ancestors"]) == {"src"}
    assert set(out["descendants"]) == {"mdl"}
