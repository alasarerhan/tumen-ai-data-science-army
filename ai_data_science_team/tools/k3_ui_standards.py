"""
k3_ui_standards
==============

Deterministic tools supporting **K3 — UI Standartları & Design
System** (spec ``docs/specs/K3-ui-standards.md``).

The K3 Design System is the canonical UI layer that every screen
consumes; the React components live in
``frontend/src/components/k3/``. This Python module exposes the
*catalog* and *theme tokens* so backend tooling (streaming
contract validation, agent-progress serializer, theming
introspection) can depend on stable identifiers.

Public surface
--------------

* :func:`COMPONENT_CATALOG` — the canonical component registry
  (DataTable, MetricCard, StatusBadge, DiffView, …).
* :func:`component_spec` — return the spec dict for one component.
* :func:`list_components` — return sorted list of component ids.
* :func:`THEME_TOKENS` — light + dark token palettes.
* :func:`resolve_theme` — return token dict for ``light`` or ``dark``.
* :func:`STREAMING_PROGRESS_STATES` — canonical states for agent
  progress streaming (used to validate streaming SSE messages).
* :func:`K3_UI_STANDARDS_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Component catalog
# ---------------------------------------------------------------------------


COMPONENT_CATALOG: Dict[str, Dict[str, Any]] = {
    "DataTable": {
        "name": "DataTable",
        "category": "data",
        "description": (
            "Generic paginated, sortable, filterable DataFrame viewer."
        ),
        "props_required": ["columns", "rows"],
        "props_optional": ["page_size", "searchable", "export"],
        "tokens_used": ["color-surface", "color-text", "border-radius"],
    },
    "MetricCard": {
        "name": "MetricCard",
        "category": "data",
        "description": (
            "Single-metric KPI card (label, value, sparkline, delta)."
        ),
        "props_required": ["label", "value"],
        "props_optional": ["unit", "sparkline", "delta", "target"],
        "tokens_used": ["color-primary", "color-surface", "color-positive"],
    },
    "StatusBadge": {
        "name": "StatusBadge",
        "category": "feedback",
        "description": "Coloured badge for status indicators (ok/warning/error).",
        "props_required": ["status"],
        "props_optional": ["label"],
        "tokens_used": ["color-positive", "color-warning", "color-negative"],
    },
    "DiffView": {
        "name": "DiffView",
        "category": "data",
        "description": "Side-by-side or inline diff for text/JSON.",
        "props_required": ["before", "after"],
        "props_optional": ["mode", "wrap"],
        "tokens_used": ["color-accent", "color-surface-subtle"],
    },
    "SchemaTree": {
        "name": "SchemaTree",
        "category": "data",
        "description": "Tree view for dataset/column schema with badges.",
        "props_required": ["tree"],
        "props_optional": ["selected"],
        "tokens_used": ["color-surface", "color-text"],
    },
    "CodeBlock": {
        "name": "CodeBlock",
        "category": "developer",
        "description": "Syntax-highlighted code viewer with copy button.",
        "props_required": ["code", "language"],
        "props_optional": ["max_height"],
        "tokens_used": ["color-surface", "color-text"],
    },
    "ChartContainer": {
        "name": "ChartContainer",
        "category": "data",
        "description": (
            "Themed wrapper that injects dark/light tokens into the "
            "underlying charting library (ECharts)."
        ),
        "props_required": ["kind"],
        "props_optional": ["data", "options"],
        "tokens_used": [
            "color-primary",
            "color-text",
            "color-grid",
        ],
    },
}


def component_spec(component_id: str) -> Dict[str, Any]:
    """Return the spec for a single component, or a fallback dict."""
    if component_id not in COMPONENT_CATALOG:
        return {
            "name": component_id,
            "category": "uncatalogued",
            "description": "",
            "props_required": [],
            "props_optional": [],
            "tokens_used": [],
            "_unknown": True,
        }
    return {k: v for k, v in COMPONENT_CATALOG[component_id].items()}


def list_components(
    category: Optional[str] = None,
) -> List[str]:
    """Return sorted component ids, optionally filtered by category."""
    if category is None:
        return sorted(COMPONENT_CATALOG)
    return sorted(
        cid for cid, spec in COMPONENT_CATALOG.items()
        if spec.get("category") == category
    )


# ---------------------------------------------------------------------------
# Theme tokens
# ---------------------------------------------------------------------------


# Light + dark palettes. Tokens map to the frontend CSS custom
# properties documented in the design-system styleguide.
THEME_TOKENS: Dict[str, Dict[str, str]] = {
    "light": {
        "color-bg": "#ffffff",
        "color-surface": "#f7f7fa",
        "color-surface-subtle": "#fafafc",
        "color-text": "#1c1c1e",
        "color-text-muted": "#6b6b73",
        "color-primary": "#3a6df0",
        "color-positive": "#16a34a",
        "color-warning": "#f59e0b",
        "color-negative": "#dc2626",
        "color-accent": "#7c3aed",
        "color-grid": "#e5e7eb",
        "color-border": "#d6d6db",
        "border-radius": "8px",
    },
    "dark": {
        "color-bg": "#0f1115",
        "color-surface": "#181c22",
        "color-surface-subtle": "#1c2129",
        "color-text": "#e7e9ef",
        "color-text-muted": "#9aa1ac",
        "color-primary": "#7e9bfa",
        "color-positive": "#3ecf8e",
        "color-warning": "#f5b94e",
        "color-negative": "#ef6b6b",
        "color-accent": "#a78bfa",
        "color-grid": "#2a2f37",
        "color-border": "#2a2f37",
        "border-radius": "8px",
    },
}


def resolve_theme(theme: str = "light") -> Dict[str, str]:
    """Return the token dict for the requested theme."""
    if theme not in THEME_TOKENS:
        raise ValueError(
            f"Unknown theme '{theme}'. Known: {sorted(THEME_TOKENS)}"
        )
    return dict(THEME_TOKENS[theme])


# ---------------------------------------------------------------------------
# Streaming-progress canonical states
# ---------------------------------------------------------------------------


# These are the streaming states the agent runtime commits to. Any
# SSE payload that emits a state outside this set is rejected by the
# frontend transport validator.
STREAMING_PROGRESS_STATES: List[str] = [
    "started",
    "thinking",
    "tool_call",
    "tool_result",
    "warning",
    "stream_chunk",
    "complete",
    "error",
    "cancelled",
]


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


@dataclass
class StreamingProgressEvent:
    event_id: str
    state: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp_ms: int = 0


def validate_streaming_state(state: str) -> bool:
    """Return True if ``state`` is a known streaming-progress state."""
    return state in STREAMING_PROGRESS_STATES


# ---------------------------------------------------------------------------
# Component/token lint
# ---------------------------------------------------------------------------


def lint_component_props(
    component_id: str,
    provided_props: Mapping[str, Any],
) -> List[str]:
    """Return the list of required props that ``provided_props`` is missing."""
    spec = component_spec(component_id)
    required = spec.get("props_required") or []
    missing = [
        str(p) for p in required
        if p not in provided_props or provided_props.get(p) in (None, "")
    ]
    return missing


__all__ = [
    "COMPONENT_CATALOG",
    "component_spec",
    "list_components",
    "THEME_TOKENS",
    "resolve_theme",
    "STREAMING_PROGRESS_STATES",
    "validate_streaming_state",
    "lint_component_props",
    "K3_UI_STANDARDS_TOOL_NAMES",
]


K3_UI_STANDARDS_TOOL_NAMES = [
    "k3_component_spec",
    "k3_list_components",
    "k3_resolve_theme",
    "k3_validate_streaming_state",
    "k3_lint_component_props",
]
