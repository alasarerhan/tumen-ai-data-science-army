from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any

from platform_api.services.workflow_node_catalog_service import get_workflow_node_catalog_by_type

TRIGGER_TYPES = {
    "manual.trigger",
    "schedule.trigger",
    "webhook.trigger",
    "dataset-uploaded.trigger",
    "drift-detected.trigger",
}


def adapt_workflow_spec_to_v2(spec: dict[str, Any]) -> dict[str, Any]:
    """Return a Workflow IR v2-shaped document without mutating legacy specs."""
    if spec.get("ir_version") == "2.0":
        return deepcopy(spec)

    if isinstance(spec.get("graph"), dict):
        graph = spec["graph"]
        return {
            "ir_version": "2.0",
            "name": spec.get("name", "Workflow"),
            "description": spec.get("description"),
            "triggers": spec.get("triggers")
            or [{"id": "trigger.manual", "type": "manual.trigger", "config": {}}],
            "nodes": graph.get("nodes", []),
            "edges": graph.get("edges", []),
            "inputs": spec.get("inputs", []),
            "outputs": spec.get("outputs", []),
            "resources": spec.get("resources", {}),
            "timeout_seconds": spec.get("timeout_seconds"),
            "retry_policy": spec.get("retry_policy", {"max_attempts": 1, "backoff_seconds": 30}),
            "fallback_policy": spec.get("fallback_policy", {}),
            "approval_policy": spec.get("approval_policy", spec.get("hitl_config", {})),
            "legacy_spec": deepcopy(spec),
        }

    steps = spec.get("steps") if isinstance(spec.get("steps"), list) else []
    nodes = []
    edges = []
    for step in steps:
        node_id = str(step.get("id") or step.get("name") or f"node-{len(nodes) + 1}")
        node_type = str(step.get("type") or step.get("agent") or "report.generate")
        nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "config": {"instruction": step.get("instruction")},
                "inputs": step.get("inputs", []),
                "outputs": step.get("outputs", []),
                "resources": step.get("resources", {}),
                "timeout_seconds": step.get("timeout_seconds"),
                "retry_policy": step.get("retry_policy", {}),
                "fallback_policy": {"fallbacks": step.get("fallbacks", [])},
                "approval_policy": step.get("approval_policy", {}),
            }
        )
        for dependency in step.get("depends_on", []) or []:
            edges.append({"source": str(dependency), "target": node_id})

    return {
        "ir_version": "2.0",
        "name": spec.get("name", "Workflow"),
        "description": spec.get("description"),
        "triggers": spec.get("triggers")
        or [{"id": "trigger.manual", "type": "manual.trigger", "config": {}}],
        "nodes": nodes,
        "edges": edges,
        "inputs": spec.get("inputs", []),
        "outputs": spec.get("outputs", []),
        "resources": spec.get("resources", {}),
        "timeout_seconds": spec.get("timeout_seconds"),
        "retry_policy": spec.get("retry_policy", {"max_attempts": 1, "backoff_seconds": 30}),
        "fallback_policy": spec.get("fallback_policy", {}),
        "approval_policy": spec.get("approval_policy", spec.get("hitl_config", {})),
        "legacy_spec": deepcopy(spec),
    }


def validate_workflow_ir_v2(spec: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    catalog = get_workflow_node_catalog_by_type()
    document = adapt_workflow_spec_to_v2(spec)
    nodes = document.get("nodes") if isinstance(document.get("nodes"), list) else []
    triggers = document.get("triggers") if isinstance(document.get("triggers"), list) else []
    edges = document.get("edges") if isinstance(document.get("edges"), list) else []
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not triggers:
        errors.append(
            {
                "code": "missing_trigger",
                "message": "Workflow IR v2 requires at least one trigger node",
            }
        )

    node_ids: set[str] = set()
    for trigger in triggers:
        trigger_type = str(trigger.get("type", ""))
        if trigger_type not in catalog and trigger_type not in TRIGGER_TYPES:
            errors.append(
                {
                    "code": "unknown_trigger_type",
                    "message": f"Unsupported trigger type: {trigger_type}",
                }
            )

    for node in nodes:
        node_id = str(node.get("id", ""))
        node_type = str(
            node.get("type")
            or node.get("data", {}).get("type")
            or node.get("data", {}).get("agent")
            or ""
        )
        if not node_id:
            errors.append(
                {"code": "missing_node_id", "message": "Every workflow node requires an id"}
            )
            continue
        if node_id in node_ids:
            errors.append(
                {"code": "duplicate_node_id", "message": f"Duplicate workflow node id: {node_id}"}
            )
        node_ids.add(node_id)
        if node_type not in catalog:
            errors.append(
                {
                    "code": "unknown_node_type",
                    "message": f"Unsupported node type for {node_id}: {node_type}",
                }
            )

    adjacency: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = defaultdict(int)
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in node_ids:
            warnings.append(
                {
                    "code": "edge_source_not_node",
                    "message": f"Edge source is not a workflow node: {source}",
                }
            )
        if target not in node_ids:
            errors.append(
                {
                    "code": "edge_target_not_node",
                    "message": f"Edge target is not a workflow node: {target}",
                }
            )
        if source and target:
            adjacency[source].append(target)
            incoming[target] += 1

    if _has_cycle(node_ids, adjacency):
        errors.append({"code": "cycle_detected", "message": "Workflow graph must be acyclic"})

    supplied_inputs = {
        str(item.get("artifact_type"))
        for item in document.get("inputs", [])
        if isinstance(item, dict)
    }
    for node in nodes:
        node_type = str(
            node.get("type")
            or node.get("data", {}).get("type")
            or node.get("data", {}).get("agent")
            or ""
        )
        contract = catalog.get(node_type)
        if not contract:
            continue
        required_inputs = [
            item
            for item in contract.get("inputs", [])
            if item.get("required") and item.get("artifact_type") not in {"any", "trigger_context"}
        ]
        if required_inputs and incoming[str(node.get("id"))] == 0:
            missing = ", ".join(
                str(item["artifact_type"])
                for item in required_inputs
                if str(item["artifact_type"]) not in supplied_inputs
            )
            if missing:
                errors.append(
                    {
                        "code": "missing_required_input",
                        "message": f"{node.get('id')} requires input artifact type(s): {missing}",
                    }
                )

    return {"errors": errors, "warnings": warnings}


def _has_cycle(node_ids: set[str], adjacency: dict[str, list[str]]) -> bool:
    indegree = {node_id: 0 for node_id in node_ids}
    for targets in adjacency.values():
        for target in targets:
            if target in indegree:
                indegree[target] += 1
    queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in adjacency.get(node_id, []):
            if target not in indegree:
                continue
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return visited != len(indegree)
