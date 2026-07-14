"""
Tests for ``ai_data_science_team.tools.k1_designer`` (K1 tool layer).
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.k1_designer import (
    ZONE_ORDER,
    assign_flow_zones,
    inline_validation_markers,
    node_metadata,
    version_diff,
)


def _plan(node_specs, edges=None):
    return {
        "nodes": [
            {"id": str(nid), "type": t, "config": cfg}
            for nid, (t, cfg) in node_specs.items()
        ],
        "edges": edges or [],
    }


class TestAssignFlowZones:
    def test_basic_zone_grouping(self):
        plan = _plan(
            {
                "load": ("data.load", {"dataset": "x"}),
                "transform": ("data.transform", {"operations": []}),
                "train": ("model.train", {"dataset": "x", "target": "y", "engine": "xgboost"}),
                "write": ("data.write", {"dataset": "x", "target": "table"}),
            }
        )
        result = assign_flow_zones(plan)
        zones = result["zones"]
        # Ingest/Prep/Train/Evaluate/Deploy as expected
        assert "load" in zones["ingest"]
        assert "transform" in zones["prep"]
        assert "train" in zones["train"]
        assert "write" in zones["deploy"]
        assert result["zone_order"] == ZONE_ORDER

    def test_orphan_zone_for_unknown_node_type(self):
        plan = _plan(
            {
                "a": ("some.weird.type", {}),
                "b": ("data.load", {"dataset": "x"}),
            }
        )
        result = assign_flow_zones(plan)
        assert "a" in result["zones"]["other"]
        assert "b" in result["zones"]["ingest"]
        assert "a" in result["orphans"]

    def test_node_cards_populated(self):
        plan = _plan(
            {"a": ("data.load", {"dataset": "x"})}
        )
        result = assign_flow_zones(plan)
        cards = result["node_cards"]
        assert len(cards) == 1
        assert cards[0]["type"] == "data.load"
        assert cards[0]["zone"] == "ingest"


class TestNodeMetadata:
    def test_required_params_surface(self):
        node = {
            "id": "n1",
            "type": "model.train",
            "config": {"dataset": "x"},  # missing target + engine
        }
        meta = node_metadata(node, required_params=["dataset", "target", "engine"])
        assert "target" in meta.missing_required_params
        assert "engine" in meta.missing_required_params
        assert "dataset" not in meta.missing_required_params

    def test_config_keys_sorted(self):
        node = {
            "id": "n1",
            "type": "x.y",
            "config": {"z": 1, "a": 2, "m": 3},
        }
        meta = node_metadata(node)
        assert meta.config_keys == ["a", "m", "z"]

    def test_zone_derived(self):
        node = {"id": "a", "type": "model.predict", "config": {}}
        meta = node_metadata(node)
        assert meta.zone == "evaluate"

    def test_sample_preview_capped_at_20(self):
        node = {"id": "a", "type": "x", "config": {}, "preview": list(range(30))}
        meta = node_metadata(node)
        assert len(meta.sample_preview) == 20


class TestVersionDiff:
    def test_added_removed_changed(self):
        left = _plan(
            {
                "a": ("data.load", {"dataset": "x"}),
                "b": ("data.load", {"dataset": "y"}),
            }
        )
        right = _plan(
            {
                "a": ("data.load", {"dataset": "x"}),
                "b": ("data.load", {"dataset": "z"}),
                "c": ("data.write", {"dataset": "x", "target": "t"}),
            }
        )
        diff = version_diff(left, right)
        assert diff["added"] == ["c"]
        assert diff["removed"] == []
        assert any(d["id"] == "b" for d in diff["changed"])

    def test_removed_only(self):
        left = _plan(
            {
                "a": ("data.load", {"dataset": "x"}),
                "b": ("data.load", {"dataset": "y"}),
            }
        )
        right = _plan(
            {"a": ("data.load", {"dataset": "x"})}
        )
        diff = version_diff(left, right)
        assert diff["removed"] == ["b"]


class TestInlineValidationMarkers:
    def test_passes_through_issues(self):
        issues = [
            {
                "severity": "error",
                "code": "missing_required_param",
                "message": "Need target.",
                "node_id": "n1",
            }
        ]
        markers = inline_validation_markers(issues)
        assert markers[0]["code"] == "missing_required_param"
        assert markers[0]["node_id"] == "n1"

    def test_filters_non_mappings(self):
        issues = [
            "not a mapping",
            {"severity": "warning", "code": "x", "message": "y", "node_id": "n1"},
        ]
        markers = inline_validation_markers(issues)
        assert len(markers) == 1
