"""Tests for ``ai_data_science_team.tools.dashboard`` (C2 tool layer)."""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.dashboard import (
    add_panel,
    make_dashboard,
    make_share_token,
    render_snapshot,
    validate_layout,
)


class TestAddPanel:
    def test_basic(self):
        dash = make_dashboard("kpi", [], grid_rows=2, grid_cols=2)
        panel = add_panel(
            dash,
            title="t",
            artifact_ref="a/b",
            row=0,
            col=0,
        )
        assert panel.panel_id in {p.panel_id for p in dash.panels}
        assert panel.width == 1
        assert panel.height == 1

    def test_out_of_bounds(self):
        dash = make_dashboard("kpi", [], grid_rows=2, grid_cols=2)
        with pytest.raises(ValueError):
            add_panel(dash, title="t", artifact_ref="x", row=2, col=0)

    def test_overlap_rejected(self):
        dash = make_dashboard("kpi", [], grid_rows=4, grid_cols=4)
        add_panel(dash, title="a", artifact_ref="x", row=0, col=0)
        with pytest.raises(ValueError):
            add_panel(dash, title="b", artifact_ref="y", row=0, col=0)

    def test_side_by_side_no_overlap(self):
        dash = make_dashboard("kpi", [], grid_rows=4, grid_cols=4)
        add_panel(dash, title="a", artifact_ref="x", row=0, col=0)
        add_panel(dash, title="b", artifact_ref="y", row=0, col=2)
        assert len(dash.panels) == 2


class TestValidateLayout:
    def test_valid(self):
        dash = make_dashboard(
            "kpi",
            [
                {"title": "a", "artifact_ref": "x", "row": 0, "col": 0},
                {"title": "b", "artifact_ref": "y", "row": 0, "col": 2},
            ],
            grid_rows=2,
            grid_cols=4,
        )
        assert validate_layout(dash) == []

    def test_detects_overlap_when_panels_dragged(self):
        # Construct a dashboard with two non-overlapping panels
        # then add a third that overlaps one of them.
        dash = make_dashboard(
            "kpi",
            [
                {"title": "a", "artifact_ref": "x", "row": 0, "col": 0},
                {"title": "b", "artifact_ref": "y", "row": 0, "col": 2},
            ],
            grid_rows=2,
            grid_cols=4,
        )
        # bypass add_panel checks: mutate directly
        dash.panels[0].width = 3  # now overlaps with the second
        assert any(
            "overlap" in issue for issue in validate_layout(dash)
        )


class TestShareToken:
    def test_deterministic(self):
        dash = make_dashboard(
            "kpi",
            [
                {"title": "a", "artifact_ref": "x", "row": 0, "col": 0},
            ],
            grid_rows=2,
            grid_cols=2,
        )
        t1 = make_share_token(dash)
        t2 = make_share_token(dash)
        assert t1 == t2
        assert len(t1) == 24

    def test_different_dashboards_different_token(self):
        a = make_dashboard("a", [])
        b = make_dashboard("b", [])
        assert make_share_token(a) != make_share_token(b)


class TestRenderSnapshot:
    def test_includes_panels(self):
        dash = make_dashboard(
            "kpi",
            [
                {"title": "alpha", "artifact_ref": "a", "row": 0, "col": 0, "chart_type": "line"},
                {"title": "beta", "artifact_ref": "b", "row": 1, "col": 0, "chart_type": "bar"},
            ],
            grid_rows=2,
            grid_cols=2,
        )
        snap = render_snapshot(dash)
        assert "kpi" in snap
        assert "alpha" in snap
        assert "beta" in snap
        assert "Layout: valid" in snap

    def test_share_token_included(self):
        dash = make_dashboard("k", [])
        dash.share_token = "abc123"
        snap = render_snapshot(dash)
        assert "abc123" in snap

    def test_layout_issues_included(self):
        # Add an out-of-bounds panel via Panel class.
        from ai_data_science_team.tools.dashboard import Panel
        dash = make_dashboard("k", [])
        dash.panels.append(
            Panel(
                panel_id="p1",
                title="t",
                artifact_ref="a",
                row=99,  # out of bounds
                col=0,
                width=1,
                height=1,
                chart_type="line",
            )
        )
        snap = render_snapshot(dash)
        # Either explicit "Layout issues" or specific issue text.
        assert "Layout issues" in snap or "extends past" in snap


class TestMakeDashboard:
    def test_one_shot(self):
        dash = make_dashboard(
            "d1",
            [
                {"title": "a", "artifact_ref": "a", "row": 0, "col": 0},
                {"title": "b", "artifact_ref": "b", "row": 0, "col": 1},
            ],
            grid_rows=1,
            grid_cols=2,
            dashboard_id="my-id",
        )
        assert dash.dashboard_id == "my-id"
        assert len(dash.panels) == 2

    def test_auto_id(self):
        dash = make_dashboard("d", [])
        assert dash.dashboard_id.startswith("d_")
