"""
Tests for ``ai_data_science_team.tools.k3_ui_standards`` (K3 tool layer).
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.k3_ui_standards import (
    COMPONENT_CATALOG,
    STREAMING_PROGRESS_STATES,
    THEME_TOKENS,
    component_spec,
    lint_component_props,
    list_components,
    resolve_theme,
    validate_streaming_state,
)


class TestComponentCatalog:
    def test_every_component_has_required_fields(self):
        for cid, spec in COMPONENT_CATALOG.items():
            assert "name" in spec
            assert "category" in spec
            assert "props_required" in spec

    def test_known_component_spec(self):
        spec = component_spec("DataTable")
        assert spec["name"] == "DataTable"
        assert "columns" in spec["props_required"]

    def test_unknown_component_returns_unknown_flag(self):
        spec = component_spec("NoSuchComponent")
        assert spec.get("_unknown") is True

    def test_list_components_sorted(self):
        all_components = list_components()
        assert all_components == sorted(all_components)

    def test_list_components_by_category(self):
        data_components = list_components(category="data")
        # All returned components should have category=data.
        for cid in data_components:
            assert COMPONENT_CATALOG[cid]["category"] == "data"


class TestThemeTokens:
    def test_resolve_light(self):
        tokens = resolve_theme("light")
        assert tokens["color-bg"] == "#ffffff"
        assert tokens["color-text"] == "#1c1c1e"

    def test_resolve_dark(self):
        tokens = resolve_theme("dark")
        assert tokens["color-bg"] == "#0f1115"

    def test_unknown_theme_raises(self):
        with pytest.raises(ValueError):
            resolve_theme("neon")

    def test_themes_have_same_keys(self):
        light_keys = set(resolve_theme("light"))
        dark_keys = set(resolve_theme("dark"))
        assert light_keys == dark_keys


class TestStreamingStates:
    def test_known_states_valid(self):
        for state in ("started", "tool_call", "complete", "error"):
            assert validate_streaming_state(state) is True

    def test_unknown_state_invalid(self):
        assert validate_streaming_state("pumpkin") is False

    def test_canonical_states_complete(self):
        # The canonical list is documented in the spec.
        expected = {"started", "thinking", "tool_call", "tool_result",
                    "warning", "stream_chunk", "complete", "error", "cancelled"}
        assert set(STREAMING_PROGRESS_STATES) == expected


class TestLintComponentProps:
    def test_missing_required_surfaced(self):
        missing = lint_component_props("DataTable", {"rows": []})
        assert "columns" in missing
        assert "rows" not in missing

    def test_all_required_provided(self):
        missing = lint_component_props(
            "DataTable", {"columns": [], "rows": []}
        )
        assert missing == []

    def test_empty_string_treated_as_missing(self):
        missing = lint_component_props("MetricCard", {"label": "", "value": 1})
        assert "label" in missing

    def test_unknown_component_no_required(self):
        missing = lint_component_props("NoSuchComponent", {})
        assert missing == []
