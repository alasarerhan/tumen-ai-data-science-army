"""
c2_dashboard
===========

Deterministic dashboard-composition tools supporting **C2 —
Dashboard Kompozisyonu** (spec ``docs/specs/C2-dashboard-composition.md``).

The actual drag-and-drop editor is a UI concern (out of scope for
this tool).  This module provides the deterministic core that the
``report.compose`` node executor and the shareable-URL endpoint
rely on:

  * Compose multiple chart artifacts into a single grid.
  * Validate grid layout (no overlaps, sane row/column counts).
  * Render a snapshot (a deterministic textual representation
    that the shareable-URL view renders).
  * Compute a public URL token for the dashboard.

Public surface
--------------

* :func:`add_panel` — add a chart-panel slot to a dashboard.
* :func:`validate_layout` — check overlaps + bounds.
* :func:`render_snapshot` — deterministic textual snapshot.
* :func:`make_dashboard` — one-shot constructor + shareable token.
* :func:`C2_DASHBOARD_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence



# ---------------------------------------------------------------------------
# Panel / Dashboard dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Panel:
    panel_id: str
    title: str
    artifact_ref: str
    row: int
    col: int
    width: int = 1
    height: int = 1
    chart_type: str = "line"
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "artifact_ref": self.artifact_ref,
            "row": int(self.row),
            "col": int(self.col),
            "width": int(self.width),
            "height": int(self.height),
            "chart_type": self.chart_type,
            "options": dict(self.options),
        }


@dataclass
class Dashboard:
    dashboard_id: str
    name: str
    panels: List[Panel] = field(default_factory=list)
    grid_rows: int = 4
    grid_cols: int = 4
    share_token: str = ""
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dashboard_id": self.dashboard_id,
            "name": self.name,
            "panels": [p.to_dict() for p in self.panels],
            "grid_rows": int(self.grid_rows),
            "grid_cols": int(self.grid_cols),
            "share_token": self.share_token,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Panel addition
# ---------------------------------------------------------------------------


def add_panel(
    dashboard: Dashboard,
    *,
    title: str,
    artifact_ref: str,
    row: int = 0,
    col: int = 0,
    width: int = 1,
    height: int = 1,
    chart_type: str = "line",
    options: Optional[Mapping[str, Any]] = None,
) -> Panel:
    """Add a chart panel to a dashboard and return it.

    Validates that the panel fits within the grid and that the cell
    range is non-overlapping.  Raises ``ValueError`` on bad input.
    """
    if width <= 0 or height <= 0:
        raise ValueError("panel width/height must be positive")
    if row < 0 or col < 0:
        raise ValueError("row/col must be non-negative")
    if row + height > dashboard.grid_rows:
        raise ValueError("panel extends past grid_rows")
    if col + width > dashboard.grid_cols:
        raise ValueError("panel extends past grid_cols")
    pid = f"p_{uuid.uuid4().hex[:8]}"
    panel = Panel(
        panel_id=pid,
        title=title,
        artifact_ref=artifact_ref,
        row=row,
        col=col,
        width=width,
        height=height,
        chart_type=chart_type,
        options=dict(options or {}),
    )
    if _overlaps(panel, dashboard.panels):
        raise ValueError(
            f"panel {pid} ({row},{col})+{width}x{height} overlaps an "
            "existing panel"
        )
    dashboard.panels.append(panel)
    return panel


# ---------------------------------------------------------------------------
# Validation + shareable token + snapshot
# ---------------------------------------------------------------------------


def validate_layout(dashboard: Dashboard) -> List[str]:
    """Return a list of layout issues (empty list = valid)."""
    issues: List[str] = []
    if dashboard.grid_rows < 1 or dashboard.grid_cols < 1:
        issues.append("grid_rows / grid_cols must be positive")
    seen_ids: set = set()
    for panel in dashboard.panels:
        if panel.panel_id in seen_ids:
            issues.append(f"duplicate panel_id {panel.panel_id}")
        seen_ids.add(panel.panel_id)
        if panel.row < 0 or panel.col < 0:
            issues.append(f"{panel.panel_id} has negative row/col")
        if panel.row + panel.height > dashboard.grid_rows:
            issues.append(
                f"{panel.panel_id} extends past grid_rows"
            )
        if panel.col + panel.width > dashboard.grid_cols:
            issues.append(
                f"{panel.panel_id} extends past grid_cols"
            )
        if panel.width <= 0 or panel.height <= 0:
            issues.append(
                f"{panel.panel_id} has non-positive size"
            )
    if _has_overlaps(dashboard.panels):
        issues.append("panels overlap")
    return issues


def make_share_token(
    dashboard: Dashboard, *, secret: str = "platform-share"
) -> str:
    """Compute a deterministic share token from a dashboard snapshot."""
    payload = json.dumps(dashboard.to_dict(), sort_keys=True, default=str)
    raw = (secret + "|" + payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def render_snapshot(dashboard: Dashboard) -> str:
    """Render a deterministic textual snapshot of the dashboard.

    The shareable-URL view renders this to HTML or PDF; the test
    suite asserts on the textual content.
    """
    lines: List[str] = []
    lines.append(f"Dashboard: {dashboard.name} ({dashboard.dashboard_id})")
    lines.append(
        f"Grid: {dashboard.grid_rows} rows x {dashboard.grid_cols} cols"
    )
    if dashboard.share_token:
        lines.append(f"Share token: {dashboard.share_token}")
    issues = validate_layout(dashboard)
    if issues:
        lines.append(f"Layout issues: {issues}")
    else:
        lines.append("Layout: valid")
    lines.append(f"Panels ({len(dashboard.panels)}):")
    # Sort by (row, col) for deterministic output
    for panel in sorted(
        dashboard.panels, key=lambda p: (p.row, p.col, p.panel_id)
    ):
        lines.append(
            "  - {pid} {title!r} type={ctype} at ({row},{col}) "
            "{w}x{h} ref={ref}".format(
                pid=panel.panel_id,
                title=panel.title,
                ctype=panel.chart_type,
                row=panel.row,
                col=panel.col,
                w=panel.width,
                h=panel.height,
                ref=panel.artifact_ref,
            )
        )
    return "\n".join(lines)


def make_dashboard(
    name: str,
    panels: Sequence[Mapping[str, Any]],
    *,
    grid_rows: int = 4,
    grid_cols: int = 4,
    share_token: str = "",
    dashboard_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dashboard:
    """One-shot constructor that materialises a dashboard from a list
    of panel dicts.
    """
    dash = Dashboard(
        dashboard_id=dashboard_id or f"d_{uuid.uuid4().hex[:8]}",
        name=name,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        share_token=share_token,
        created_at=created_at,
    )
    for panel_dict in panels:
        add_panel(
            dash,
            title=panel_dict.get("title", ""),
            artifact_ref=panel_dict.get("artifact_ref", ""),
            row=panel_dict.get("row", 0),
            col=panel_dict.get("col", 0),
            width=panel_dict.get("width", 1),
            height=panel_dict.get("height", 1),
            chart_type=panel_dict.get("chart_type", "line"),
            options=panel_dict.get("options"),
        )
    return dash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _overlaps(panel: Panel, others: Sequence[Panel]) -> bool:
    for o in others:
        if o.panel_id == panel.panel_id:
            continue
        if _rects_overlap(panel, o):
            return True
    return False


def _has_overlaps(panels: Sequence[Panel]) -> bool:
    seen: List[Panel] = []
    for p in panels:
        if _overlaps(p, seen):
            return True
        seen.append(p)
    return False


def _rects_overlap(a: Panel, b: Panel) -> bool:
    if a.row + a.height <= b.row or b.row + b.height <= a.row:
        return False
    if a.col + a.width <= b.col or b.col + b.width <= a.col:
        return False
    return True


__all__ = [
    "Panel",
    "Dashboard",
    "add_panel",
    "validate_layout",
    "make_share_token",
    "render_snapshot",
    "make_dashboard",
    "C2_DASHBOARD_TOOL_NAMES",
]


C2_DASHBOARD_TOOL_NAMES = [
    "c2_add_panel",
    "c2_validate_layout",
    "c2_render_snapshot",
    "c2_make_share_token",
    "c2_make_dashboard",
]
