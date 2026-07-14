"""j12_lineage. Deterministic end-to-end lineage graph tools.
Implements J12 — record source→dataset→feature→model→deployment→report
nodes and their edges; query ancestors / descendants; render a
graph payload for the UI; impact-analysis mode that highlights all
downstream nodes.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


VALID_KINDS: Set[str] = {
    "source", "dataset", "feature", "model", "deployment", "report",
}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class LineageNode:
    node_id: str
    kind: str
    label: str
    attrs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageEdge:
    source: str
    target: str
    relation: str = "produces"


@dataclass
class LineageGraph:
    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)

    def add_node(self, n: LineageNode) -> None:
        self.nodes.append(n)

    def add_edge(self, e: LineageEdge) -> None:
        self.edges.append(e)


def add_node(
    graph: LineageGraph,
    *,
    kind: str,
    label: str,
    attrs: Optional[Mapping[str, Any]] = None,
    node_id: Optional[str] = None,
) -> LineageNode:
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(VALID_KINDS)}")
    n = LineageNode(
        node_id=node_id or _new_id(),
        kind=kind,
        label=label,
        attrs=dict(attrs or {}),
    )
    graph.add_node(n)
    return n


def add_edge(
    graph: LineageGraph, source: str, target: str, relation: str = "produces"
) -> LineageEdge:
    src_ids = {n.node_id for n in graph.nodes}
    if source not in src_ids:
        raise KeyError(f"source node_id not found: {source}")
    if target not in src_ids:
        raise KeyError(f"target node_id not found: {target}")
    e = LineageEdge(source=source, target=target, relation=relation)
    graph.add_edge(e)
    return e


def _adjacency(graph: LineageGraph) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """Return (outgoing, incoming) adjacency dicts keyed by node_id."""
    out: Dict[str, List[str]] = {n.node_id: [] for n in graph.nodes}
    inc: Dict[str, List[str]] = {n.node_id: [] for n in graph.nodes}
    for e in graph.edges:
        out.setdefault(e.source, []).append(e.target)
        inc.setdefault(e.target, []).append(e.source)
    return out, inc


def ancestors(graph: LineageGraph, node_id: str) -> List[str]:
    """All upstream node_ids via BFS over incoming edges."""
    _, inc = _adjacency(graph)
    seen: Set[str] = set()
    queue: List[str] = list(inc.get(node_id, []))
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        queue.extend(inc.get(cur, []))
    return sorted(seen)


def descendants(graph: LineageGraph, node_id: str) -> List[str]:
    """All downstream node_ids via BFS over outgoing edges."""
    out, _ = _adjacency(graph)
    seen: Set[str] = set()
    queue: List[str] = list(out.get(node_id, []))
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        queue.extend(out.get(cur, []))
    return sorted(seen)


def render_graph(
    graph: LineageGraph,
    *,
    highlight_node: Optional[str] = None,
    mode: str = "full",
) -> Dict[str, Any]:
    """Build a UI-ready dict. mode='impact' highlights all
    descendants of highlight_node."""
    nodes = [
        {"id": n.node_id, "kind": n.kind, "label": n.label,
         "attrs": n.attrs}
        for n in graph.nodes
    ]
    edges = [
        {"source": e.source, "target": e.target, "relation": e.relation}
        for e in graph.edges
    ]
    highlight: List[str] = []
    if highlight_node is not None:
        highlight = [highlight_node] + descendants(graph, highlight_node)
    return {
        "nodes": nodes,
        "edges": edges,
        "highlight": highlight,
        "mode": mode,
    }


def node_summary(graph: LineageGraph, node_id: str) -> Dict[str, Any]:
    """Return a single node + ancestors + descendants summary."""
    n = next((n for n in graph.nodes if n.node_id == node_id), None)
    if n is None:
        raise KeyError(f"node_id not found: {node_id}")
    return {
        "node": {"id": n.node_id, "kind": n.kind, "label": n.label,
                 "attrs": n.attrs},
        "ancestors": ancestors(graph, node_id),
        "descendants": descendants(graph, node_id),
    }


J12_LINEAGE_TOOL_NAMES: List[str] = [
    "j12_add_node",
    "j12_add_edge",
    "j12_ancestors",
    "j12_descendants",
    "j12_render_graph",
    "j12_node_summary",
]
