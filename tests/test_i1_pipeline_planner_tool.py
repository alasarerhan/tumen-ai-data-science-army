"""
Tests for ``ai_data_science_team.tools.i1_pipeline_planner`` (I1 tool layer).
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.i1_pipeline_planner import (
    PlanValidationResult,
    autorepair_loop,
    chat_guide_starter,
    diff_plans,
    node_required_params,
    validate_plan,
)


def _plan(node_specs, edges=None):
    return {
        "nodes": [{"id": str(nid), "type": t, **cfg} for nid, (t, cfg) in node_specs.items()],
        "edges": edges or [],
    }


class TestValidatePlan:
    def test_minimal_valid_plan(self):
        plan = _plan(
            {
                1: (
                    "data.load",
                    {"id": 1, "type": "data.load", "config": {"dataset": "x"}},
                ),
            }
        )
        result = validate_plan(plan)
        assert result.is_valid is True

    def test_missing_required_param_detected(self):
        plan = _plan(
            {
                1: (
                    "model.train",
                    {
                        "id": 1,
                        "type": "model.train",
                        "config": {"dataset": "x"},  # missing target + engine
                    },
                ),
            }
        )
        result = validate_plan(plan)
        assert result.is_valid is False
        assert any(i.code == "missing_required_param" for i in result.issues)

    def test_duplicate_node_id(self):
        plan = {
            "nodes": [
                {
                    "id": "a",
                    "type": "data.load",
                    "config": {"dataset": "x"},
                },
                {
                    "id": "a",  # duplicate id
                    "type": "data.load",
                    "config": {"dataset": "y"},
                },
            ],
            "edges": [],
        }
        result = validate_plan(plan)
        assert any(i.code == "duplicate_id" for i in result.issues)
        assert result.is_valid is False

    def test_empty_plan_rejected(self):
        plan = {"nodes": [], "edges": []}
        result = validate_plan(plan)
        assert result.is_valid is False
        assert any(i.code == "empty_plan" for i in result.issues)

    def test_cycle_detected(self):
        plan = {
            "nodes": [
                {
                    "id": "1",
                    "type": "data.load",
                    "config": {"dataset": "a"},
                },
                {
                    "id": "2",
                    "type": "data.load",
                    "config": {"dataset": "b"},
                },
            ],
            "edges": [
                {"from": "1", "to": "2"},
                {"from": "2", "to": "1"},
            ],
        }
        result = validate_plan(plan)
        assert any(i.code == "cycle_detected" for i in result.issues)
        assert result.is_valid is False

    def test_unknown_node_type_warns(self):
        plan = _plan(
            {
                1: ("x.y", {"id": 1, "type": "x.y", "config": {}}),
            }
        )
        result = validate_plan(plan)
        assert result.is_valid is True  # warnings do not block
        assert any(i.code == "unknown_node_type" for i in result.issues)

    def test_edge_with_unknown_endpoint(self):
        plan = _plan(
            {
                1: ("data.load", {"id": 1, "type": "data.load", "config": {"dataset": "a"}}),
            },
            edges=[{"from": "1", "to": "999"}],
        )
        result = validate_plan(plan)
        assert any(i.code == "edge_unknown_to" for i in result.issues)
        assert result.is_valid is False


class TestNodeRequiredParams:
    def test_known_node(self):
        s = node_required_params("data.load")
        assert s["required"] == ["dataset"]

    def test_unknown_node(self):
        s = node_required_params("no.such.thing")
        assert s["_unknown"] is True
        assert s["required"] == []


class TestDiffPlans:
    def _base_plan(self):
        return _plan(
            {
                "a": ("data.load", {"id": "a", "type": "data.load", "config": {"dataset": "x"}}),
                "b": ("data.load", {"id": "b", "type": "data.load", "config": {"dataset": "y"}}),
            },
            edges=[{"from": "a", "to": "b"}],
        )

    def _added_plan(self):
        return _plan(
            {
                "a": ("data.load", {"id": "a", "type": "data.load", "config": {"dataset": "x"}}),
                "b": ("data.load", {"id": "b", "type": "data.load", "config": {"dataset": "y"}}),
                "c": ("data.write", {"id": "c", "type": "data.write", "config": {"dataset": "x", "target": "table"}}),
            },
            edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
        )

    def test_diff_added_node(self):
        diff = diff_plans(self._base_plan(), self._added_plan())
        assert diff["added"] == ["c"]
        assert diff["removed"] == []
        assert ("b", "c") in [tuple(e) for e in diff["edge_diff"]["added"]]

    def test_diff_removed_node(self):
        diff = diff_plans(self._added_plan(), self._base_plan())
        assert diff["removed"] == ["c"]
        assert diff["added"] == []

    def test_diff_changed_node(self):
        base = _plan({"a": ("data.load", {"id": "a", "type": "data.load", "config": {"dataset": "x"}})})
        rev = _plan({"a": ("data.load", {"id": "a", "type": "data.load", "config": {"dataset": "y"}})})
        diff = diff_plans(base, rev)
        assert diff["changed"] and diff["changed"][0]["id"] == "a"


class TestAutorepairLoop:
    def test_loop_terminates_when_valid(self):
        plan = _plan(
            {"a": ("data.load", {"id": "a", "type": "data.load", "config": {"dataset": "x"}})}
        )

        def fix(p, fb):
            return p

        out = autorepair_loop(plan, fix, max_attempts=2)
        assert out["status"] == "valid"
        assert out["attempts"] == 0

    def test_loop_stops_after_max_attempts(self):
        plan = _plan(
            {
                "a": (
                    "model.train",
                    {"id": "a", "type": "model.train", "config": {"dataset": "x"}},
                )
            }
        )

        def fix(p, fb):  # never fixes
            return p

        out = autorepair_loop(plan, fix, max_attempts=2)
        assert out["status"] == "still_invalid"
        assert out["attempts"] == 2

    def test_loop_propagates_planner_exception(self):
        # Start with an invalid plan so the loop exercises the planner at
        # least once before the exception trips.
        plan = _plan(
            {
                "a": (
                    "model.train",
                    {
                        "id": "a",
                        "type": "model.train",
                        "config": {"dataset": "x"},
                    },
                )
            }
        )

        def bad(p, fb):
            raise RuntimeError("simulated crash")

        out = autorepair_loop(plan, bad, max_attempts=2)
        assert out["status"] == "planner_error"
        assert "simulated crash" in out["error"]       


class TestChatGuideStarter:
    def test_returns_three_questions(self):
        starter = chat_guide_starter()
        assert len(starter) == 3
        assert {q["key"] for q in starter} == {"goal", "data", "frequency"}

    def test_each_question_has_label_and_placeholder(self):
        for q in chat_guide_starter():
            assert "label" in q
            assert "placeholder" in q
