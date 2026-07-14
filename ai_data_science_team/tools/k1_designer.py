"""
k1_designer
===========

Deterministic tools supporting **K1 — Workflow Designer 2.0** (spec
``docs/specs/K1-designer-2.md``).

Implements the *backend* portion of the Designer cockpit: flow-zone
assignment, rich-node-card metadata, version-diff projection, and
inline-validation.  UI rendering lives in the frontend (out of
scope for this layer), but the data it consumes is what this module
produces.

Public surface
--------------

* :func:`assign_flow_zones` — assign nodes to workflow phases based
  on type. Returns ``{zone: [node_ids]}`` plus the orphan list.
* :func:`node_metadata` — produce the rich-node-card metadata
  (status, schema summary, I/O sample) for a single node.
* :func:`version_diff` — two-snapshot workflow-version diff used by
  the Designer overlay.
* :func:`inline_validation_markers` — convert plan-validation issues
  into markers the canvas can render on the offending node.
* :func:`K1_DESIGNER_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Flow-zone taxonomy (spec §2: Ingest/Prep/Train/Evaluate/Deploy)
# ---------------------------------------------------------------------------


# Spec maps node types to flow zones; unknown types fall into "other".
NODE_TO_ZONE: Dict[str, str] = {
    "data.load": "ingest",
    "data.ingest": "ingest",
    "data.profile": "ingest",
    "data.transform": "prep",
    "data.validate": "prep",
    "data.diff": "prep",
    "model.train": "train",
    "model.train.nlp": "train",
    "model.train.graph": "train",
    "model.train.timeseries": "train",
    "model.train.cluster": "train",
    "model.train.or": "train",
    "model.predict": "evaluate",
    "experiment.analyze": "evaluate",
    "experiment.design": "evaluate",
    "experiment.compare": "evaluate",
    "model.compare": "evaluate",
    "model.drift.compute": "evaluate",
    "data.ingest": "ingest",
    "data.write": "deploy",
    "model.serving": "deploy",
    "deploy.shadow": "deploy",
    "trigger.configure": "deploy",
    "model.retrain.policy": "evaluate",
}


ZONE_ORDER: List[str] = [
    "ingest",
    "prep",
    "train",
    "evaluate",
    "deploy",
]


def _zone_of(node_type: str) -> str:
    return NODE_TO_ZONE.get(node_type, "other")


def assign_flow_zones(
    plan: Mapping[str, Any],
) -> Dict[str, Any]:
    """Assign nodes to flow zones and return zone→nodes map."""
    zones: Dict[str, List[str]] = {z: [] for z in ZONE_ORDER}
    zones["other"] = []
    cards: List[Dict[str, Any]] = []
    for n in plan.get("nodes") or []:
        if not isinstance(n, Mapping):
            continue
        nid = n.get("id")
        ntype = n.get("type")
        zone = _zone_of(ntype)
        if zone not in zones:
            zones[zone] = []
        zones[zone].append(nid)
        cards.append(
            {
                "id": nid,
                "type": ntype,
                "zone": zone,
            }
        )
    return {
        "zones": {z: list(v) for z, v in zones.items() if v},
        "node_cards": cards,
        "zone_order": ZONE_ORDER,
        "orphans": list(zones.get("other", [])),
    }


# ---------------------------------------------------------------------------
# Rich-node-card metadata
# ---------------------------------------------------------------------------


@dataclass
class NodeCardMetadata:
    id: str
    type: str
    status: str = "pending"
    zone: str = "other"
    config_keys: List[str] = field(default_factory=list)
    missing_required_params: List[str] = field(default_factory=list)
    input_columns: List[str] = field(default_factory=list)
    output_columns: List[str] = field(default_factory=list)
    sample_preview: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "zone": self.zone,
            "config_keys": list(self.config_keys),
            "missing_required_params": list(self.missing_required_params),
            "input_columns": list(self.input_columns),
            "output_columns": list(self.output_columns),
            "sample_preview": list(self.sample_preview),
        }


def node_metadata(
    node: Mapping[str, Any],
    required_params: Sequence[str] = (),
) -> NodeCardMetadata:
    """Produce rich metadata for a single node.

    Parameters
    ----------
    node : mapping
        ``{"id", "type", "config": {...}, "status": ?, "preview": ?}``.
    required_params : sequence of str
        Required config keys; missing ones are surfaced in
        ``missing_required_params`` (UI form-widget for spec US-3).

    Returns
    -------
    NodeCardMetadata dataclass with ``id``, ``type``, ``status``,
    ``zone``, ``config_keys``, ``missing_required_params``,
    ``input_columns``, ``output_columns``, ``sample_preview``.
    """
    cfg = node.get("config") or {}
    if not isinstance(cfg, Mapping):
        cfg = {}
    cfg_keys = sorted(str(k) for k in cfg.keys())
    missing = [
        str(k) for k in required_params
        if k not in cfg or cfg.get(k) in (None, "")
    ]
    return NodeCardMetadata(
        id=str(node.get("id", "")),
        type=str(node.get("type", "")),
        status=str(node.get("status", "pending")),
        zone=_zone_of(str(node.get("type", ""))),
        config_keys=cfg_keys,
        missing_required_params=missing,
        input_columns=[
            str(c) for c in (node.get("input_columns") or [])
        ],
        output_columns=[
            str(c) for c in (node.get("output_columns") or [])
        ],
        sample_preview=list(node.get("preview") or [])[:20],
    )


# ---------------------------------------------------------------------------
# Two-snapshot version diff (Designer overlay)
# ---------------------------------------------------------------------------


def version_diff(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> Dict[str, Any]:
    """Diff two workflow snapshots.

    ``left`` is the base snapshot, ``right`` is the new snapshot.  Returns
    ``added``, ``removed`` and ``changed`` node ids with side-by-side
    config diffs.
    """
    left_nodes = {
        str(n.get("id")): (n.get("config") or {})
        for n in (left.get("nodes") or [])
        if isinstance(n, Mapping) and n.get("id") is not None
    }
    right_nodes = {
        str(n.get("id")): (n.get("config") or {})
        for n in (right.get("nodes") or [])
        if isinstance(n, Mapping) and n.get("id") is not None
    }
    added = sorted(set(right_nodes) - set(left_nodes))
    removed = sorted(set(left_nodes) - set(right_nodes))
    changed: List[Dict[str, Any]] = []
    for nid in sorted(set(left_nodes) & set(right_nodes)):
        if dict(left_nodes[nid]) != dict(right_nodes[nid]):
            changed.append(
                {
                    "id": nid,
                    "before": left_nodes[nid],
                    "after": right_nodes[nid],
                }
            )
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "n_added": len(added),
        "n_removed": len(removed),
        "n_changed": len(changed),
    }


# ---------------------------------------------------------------------------
# Inline-validation markers for the canvas
# ---------------------------------------------------------------------------


def inline_validation_markers(
    issues: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Project plan-validation issues into per-node markers.

    Each output marker is shaped for the Designer canvas::

        {
          "node_id": "node_1",
          "severity": "error" | "warning",
          "code": "missing_required_param",
          "message": "...",
        }
    """
    markers: List[Dict[str, Any]] = []
    for i in issues:
        if not isinstance(i, Mapping):
            continue
        markers.append(
            {
                "node_id": i.get("node_id"),
                "severity": i.get("severity", "error"),
                "code": i.get("code", "unknown"),
                "message": i.get("message", ""),
            }
        )
    return markers


__all__ = [
    "NODE_TO_ZONE",
    "ZONE_ORDER",
    "assign_flow_zones",
    "node_metadata",
    "version_diff",
    "inline_validation_markers",
    "K1_DESIGNER_TOOL_NAMES",
]


K1_DESIGNER_TOOL_NAMES = [
    "k1_assign_flow_zones",
    "k1_node_metadata",
    "k1_version_diff",
    "k1_inline_validation",
]
