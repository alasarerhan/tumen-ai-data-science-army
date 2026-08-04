from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _normalize_name(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum())


@lru_cache(maxsize=1)
def _load_ruleset() -> dict[str, Any]:
    rules_path = Path(__file__).resolve().parents[1] / "config" / "agent_chain_rules.json"
    return json.loads(rules_path.read_text(encoding="utf-8"))


def get_workflow_chain_ruleset() -> dict[str, Any]:
    return _load_ruleset()


def get_workflow_agent_catalog() -> list[dict[str, str]]:
    return [
        {
            "key": str(rule.get("key") or ""),
            "label": str(rule.get("label") or ""),
            "kind": str(rule.get("kind") or ""),
            "color": str(rule.get("color") or ""),
        }
        for rule in _load_ruleset().get("agents", [])
        if isinstance(rule, dict) and rule.get("key")
    ]


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    ruleset = _load_ruleset()
    mapping: dict[str, str] = {}
    for rule in ruleset.get("agents", []):
        key = str(rule.get("key") or "").strip()
        label = str(rule.get("label") or "").strip()
        if key:
            mapping[_normalize_name(key)] = key
        if label:
            mapping[_normalize_name(label)] = key
        for alias in rule.get("aliases", []) or []:
            alias_str = str(alias).strip()
            if alias_str:
                mapping[_normalize_name(alias_str)] = key
    return mapping


@lru_cache(maxsize=1)
def _rules_by_key() -> dict[str, dict[str, Any]]:
    ruleset = _load_ruleset()
    return {
        str(rule.get("key")): rule
        for rule in ruleset.get("agents", [])
        if isinstance(rule, dict) and rule.get("key")
    }


def canonicalize_agent(candidate: str | None) -> str | None:
    if not candidate:
        return None
    return _alias_map().get(_normalize_name(candidate))


def _normalize_graph(
    spec: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    graph = spec.get("graph")
    if (
        isinstance(graph, dict)
        and isinstance(graph.get("nodes"), list)
        and isinstance(graph.get("edges"), list)
    ):
        target_variable = spec.get("target_variable")
        return (
            graph["nodes"],
            graph["edges"],
            target_variable
            if isinstance(target_variable, str) and target_variable.strip()
            else None,
        )

    steps = spec.get("steps")
    if not isinstance(steps, list):
        return [], [], None

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("id") or "").strip()
        if not step_id:
            continue
        nodes.append(
            {
                "id": step_id,
                "label": step.get("agent") or step.get("tool") or step_id,
                "agent": step.get("agent") or step.get("tool"),
                "kind": "derived",
            }
        )
        for dependency_id in step.get("depends_on") or []:
            dep = str(dependency_id).strip()
            if dep:
                edges.append(
                    {
                        "id": f"edge-{dep}-{step_id}",
                        "source": dep,
                        "target": step_id,
                    }
                )

    target_variable = spec.get("target_variable")
    return (
        nodes,
        edges,
        target_variable if isinstance(target_variable, str) and target_variable.strip() else None,
    )


def inspect_workflow_spec(spec: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    if not isinstance(spec, dict):
        return {
            "warnings": warnings,
            "errors": [{"code": "invalid_spec", "message": "spec must be an object"}],
        }

    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append({"code": "missing_name", "message": "Workflow name is required."})
        return {"warnings": warnings, "errors": errors}

    nodes, edges, target_variable = _normalize_graph(spec)
    if not nodes and not edges:
        errors.append(
            {
                "code": "invalid_graph",
                "message": "Workflow spec must include graph.nodes/graph.edges or a non-empty steps array.",
            }
        )
        return {"warnings": warnings, "errors": errors}

    if not nodes:
        errors.append(
            {"code": "empty_nodes", "message": "Workflow must contain at least one node."}
        )
        return {"warnings": warnings, "errors": errors}

    node_ids: set[str] = set()
    canonical_by_node: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            errors.append({"code": "invalid_node", "message": "Each node must be an object."})
            continue
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            errors.append({"code": "missing_node_id", "message": "Each node must include an id."})
            continue
        if node_id in node_ids:
            errors.append(
                {"code": "duplicate_node_id", "message": f"Duplicate node id detected: {node_id}"}
            )
            continue
        node_ids.add(node_id)
        canonical = canonicalize_agent(
            str(node.get("agent") or node.get("label") or "").strip() or None
        )
        if not canonical:
            errors.append(
                {
                    "code": "unknown_agent",
                    "message": f'Node "{node.get("label") or node_id}" does not map to a known agent.',
                }
            )
            continue
        canonical_by_node[node_id] = canonical

    incoming_counts: dict[str, int] = {}
    rules_by_key = _rules_by_key()

    for edge in edges:
        if not isinstance(edge, dict):
            errors.append({"code": "invalid_edge", "message": "Each edge must be an object."})
            continue
        edge_id = str(edge.get("id") or "").strip()
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not edge_id or not source or not target:
            errors.append(
                {
                    "code": "invalid_edge",
                    "message": "Each edge must include id, source, and target.",
                }
            )
            continue
        if source not in node_ids or target not in node_ids:
            errors.append(
                {"code": "dangling_edge", "message": f"Edge {edge_id} references unknown node."}
            )
            continue

        incoming_counts[target] = incoming_counts.get(target, 0) + 1

        source_key = canonical_by_node.get(source)
        target_key = canonical_by_node.get(target)
        if not source_key or not target_key:
            continue

        source_rule = rules_by_key.get(source_key, {})
        source_label = str(source_rule.get("label") or source_key)
        target_label = str(rules_by_key.get(target_key, {}).get("label") or target_key)

        if target_key in (source_rule.get("safe_next") or []):
            continue
        if target_key in (source_rule.get("conditional_next") or []):
            warnings.append(
                {
                    "code": "conditional_edge",
                    "message": f"{source_label} -> {target_label} is valid, but conditional/advisory rather than a guaranteed typed handoff.",
                }
            )
            continue
        errors.append(
            {
                "code": "blocked_edge",
                "message": f"{source_label} cannot chain directly into {target_label}.",
            }
        )

    requirements = _load_ruleset().get("requirements", {})
    for node_id, canonical in canonical_by_node.items():
        req = requirements.get(canonical, {})
        if not isinstance(req, dict):
            continue
        min_incoming = req.get("min_incoming_edges")
        if isinstance(min_incoming, int) and incoming_counts.get(node_id, 0) < min_incoming:
            label = str(rules_by_key.get(canonical, {}).get("label") or canonical)
            warnings.append(
                {
                    "code": "insufficient_inputs",
                    "message": f"{label} usually needs at least {min_incoming} inbound edges, but this node currently has {incoming_counts.get(node_id, 0)}.",
                }
            )
        if req.get("target_variable") and not target_variable:
            label = str(rules_by_key.get(canonical, {}).get("label") or canonical)
            warnings.append(
                {
                    "code": "missing_target_variable",
                    "message": f"{label} usually requires a target variable, but this workflow spec does not define one.",
                }
            )

    return {"warnings": warnings, "errors": errors}
