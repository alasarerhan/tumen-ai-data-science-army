"""Tests for J12 Lineage Graph tool."""
from __future__ import annotations

import pytest

import ai_data_science_team.tools.j12_lineage as j12


@pytest.fixture
def graph():
    return j12.LineageGraph()


@pytest.fixture
def populated_graph(graph):
    """source -> dataset -> feature -> model -> deployment -> report"""
    src = j12.add_node(graph, kind="source", label="S3 bucket")
    ds = j12.add_node(graph, kind="dataset", label="raw_events")
    feat = j12.add_node(graph, kind="feature", label="user_features")
    model = j12.add_node(graph, kind="model", label="churn_xgb")
    dep = j12.add_node(graph, kind="deployment", label="prod_xgb")
    rep = j12.add_node(graph, kind="report", label="monthly_scorecard")
    j12.add_edge(graph, src.node_id, ds.node_id)
    j12.add_edge(graph, ds.node_id, feat.node_id)
    j12.add_edge(graph, feat.node_id, model.node_id)
    j12.add_edge(graph, model.node_id, dep.node_id)
    j12.add_edge(graph, dep.node_id, rep.node_id)
    return {
        "graph": graph,
        "src": src, "ds": ds, "feat": feat,
        "model": model, "dep": dep, "rep": rep,
    }


class TestAddNode:
    def test_returns_node(self, graph):
        n = j12.add_node(graph, kind="source", label="x")
        assert n.kind == "source"
        assert n.label == "x"
        assert n.node_id != ""

    def test_invalid_kind(self, graph):
        with pytest.raises(ValueError):
            j12.add_node(graph, kind="alien", label="x")

    def test_attrs_copied(self, graph):
        n = j12.add_node(
            graph, kind="model", label="m",
            attrs={"version": "v1"},
        )
        assert n.attrs["version"] == "v1"


class TestAddEdge:
    def test_basic(self, populated_graph):
        # 5 edges were added in fixture
        assert len(populated_graph["graph"].edges) == 5

    def test_unknown_source(self, graph):
        ds = j12.add_node(graph, kind="dataset", label="d")
        with pytest.raises(KeyError):
            j12.add_edge(graph, "nope", ds.node_id)

    def test_unknown_target(self, graph):
        src = j12.add_node(graph, kind="source", label="s")
        with pytest.raises(KeyError):
            j12.add_edge(graph, src.node_id, "nope")

    def test_custom_relation(self, graph):
        a = j12.add_node(graph, kind="source", label="a")
        b = j12.add_node(graph, kind="dataset", label="b")
        e = j12.add_edge(graph, a.node_id, b.node_id, relation="feeds")
        assert e.relation == "feeds"


class TestAncestorsDescendants:
    def test_ancestors_chain(self, populated_graph):
        # model ancestors: source, dataset, feature
        anc = j12.ancestors(populated_graph["graph"],
                             populated_graph["model"].node_id)
        assert set(anc) == {
            populated_graph["src"].node_id,
            populated_graph["ds"].node_id,
            populated_graph["feat"].node_id,
        }

    def test_descendants_chain(self, populated_graph):
        # dataset descendants: feature, model, deployment, report
        desc = j12.descendants(populated_graph["graph"],
                               populated_graph["ds"].node_id)
        assert set(desc) == {
            populated_graph["feat"].node_id,
            populated_graph["model"].node_id,
            populated_graph["dep"].node_id,
            populated_graph["rep"].node_id,
        }

    def test_leaf_has_no_descendants(self, populated_graph):
        desc = j12.descendants(populated_graph["graph"],
                               populated_graph["rep"].node_id)
        assert desc == []

    def test_root_has_no_ancestors(self, populated_graph):
        anc = j12.ancestors(populated_graph["graph"],
                            populated_graph["src"].node_id)
        assert anc == []


class TestRenderGraph:
    def test_full_render(self, populated_graph):
        payload = j12.render_graph(populated_graph["graph"])
        assert payload["mode"] == "full"
        assert len(payload["nodes"]) == 6
        assert len(payload["edges"]) == 5
        assert payload["highlight"] == []

    def test_impact_render_highlights_descendants(self, populated_graph):
        payload = j12.render_graph(
            populated_graph["graph"],
            highlight_node=populated_graph["model"].node_id,
            mode="impact",
        )
        assert payload["mode"] == "impact"
        # highlight: model + descendants (deployment + report)
        assert populated_graph["model"].node_id in payload["highlight"]
        assert populated_graph["dep"].node_id in payload["highlight"]
        assert populated_graph["rep"].node_id in payload["highlight"]


class TestNodeSummary:
    def test_summary(self, populated_graph):
        s = j12.node_summary(
            populated_graph["graph"],
            populated_graph["model"].node_id,
        )
        assert s["node"]["kind"] == "model"
        assert populated_graph["src"].node_id in s["ancestors"]
        assert populated_graph["rep"].node_id in s["descendants"]

    def test_unknown(self, graph):
        with pytest.raises(KeyError):
            j12.node_summary(graph, "nope")


class TestToolNamesRegistry:
    def test_registry_complete(self):
        names = j12.J12_LINEAGE_TOOL_NAMES
        for n in ("j12_add_node", "j12_add_edge",
                  "j12_ancestors", "j12_descendants",
                  "j12_render_graph", "j12_node_summary"):
            assert n in names
