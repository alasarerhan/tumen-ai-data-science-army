"""
i1_pipeline_planner
====================

Deterministic tools supporting **I1 — LLM Pipeline Planner + Copilot**
(spec ``docs/specs/I1-llm-pipeline-planner.md``).

Companion to the LLM-driven planner agent; provides the
schema-validator, the node-level diff engine, the chat guide-starter
prompt builder, and revision-loop helpers.  All four are pure-Python
and reusable in offline tests.

Public surface
--------------

* :func:`validate_plan` — schema check + cycles + duplicate node ids.
* :func:`diff_plans` — node-level added/removed/changed diff between
  a base plan and a revised plan.
* :func:`autorepair_loop` — run the LLM in a bounded reflow loop
  until validation passes (or ``max_attempts`` is hit).
* :func:`chat_guide_starter` — produce a 3-step starter question list
  for empty chat sessions (spec US-4).
* :func:`node_required_params` — schema for which params are
  mandatory per node type (UI form-widget for "missing field" UX).
* :func:`I1_PLANNER_TOOL_NAMES` — registry constant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Node-type schema registry (the small version)
# ---------------------------------------------------------------------------


NODE_SCHEMA: Dict[str, Dict[str, Any]] = {
    "data.load": {
        "required": ["dataset"],
        "optional": ["rename", "sample_size"],
    },
    "data.profile": {
        "required": ["dataset"],
        "optional": ["scope", "sample_size"],
    },
    "data.transform": {
        "required": ["dataset"],
        "optional": ["operations"],
    },
    "data.validate": {
        "required": ["dataset"],
        "optional": ["expectations"],
    },
    "data.write": {
        "required": ["dataset", "target"],
        "optional": ["format", "table"],
    },
    "experiment.analyze": {
        "required": ["dataset", "treatment_col", "outcome_col"],
        "optional": ["alpha", "expected_lift"],
    },
    "experiment.design": {
        "required": ["metric_type"],
        "optional": ["baseline_rate", "expected_lift", "alpha", "power"],
    },
    "experiment.compare": {
        "required": ["champion_model_id", "challenger_model_id", "dataset"],
        "optional": ["alpha", "min_effect"],
    },
    "model.train": {
        "required": ["dataset", "target", "engine"],
        "optional": ["engine_params", "hpo"],
    },
    "model.predict": {
        "required": ["dataset", "model_id"],
        "optional": ["prediction_column", "include_probabilities"],
    },
    "model.compare": {
        "required": ["champion_model_id", "challenger_model_id", "dataset"],
        "optional": ["alpha", "min_effect"],
    },
    "run.cost.optimize": {"required": ["run_id"], "optional": []},
    "data.ingest": {"required": ["source", "target"], "optional": []},
}


def node_required_params(node_type: str) -> Dict[str, Any]:
    """Return the required/optional schema for a node type."""
    if node_type not in NODE_SCHEMA:
        return {"required": [], "optional": [], "_unknown": True}
    return {
        "required": list(NODE_SCHEMA[node_type]["required"]),
        "optional": list(NODE_SCHEMA[node_type].get("optional", [])),
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class PlanIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    node_id: Optional[str] = None


@dataclass
class PlanValidationResult:
    is_valid: bool
    issues: List[PlanIssue] = field(default_factory=list)
    missing_required_params: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": [
                {
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                    "node_id": i.node_id,
                }
                for i in self.issues
            ],
            "missing_required_params": self.missing_required_params,
        }


def _ensure_dict(node: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(node) if isinstance(node, Mapping) else {}


def validate_plan(plan: Mapping[str, Any]) -> PlanValidationResult:
    """Validate a workflow plan artifact.

    Parameters
    ----------
    plan : mapping
        ``{"nodes": [...], "edges": [...]}``. Each node is expected to
        have at least ``id`` and ``type``.

    Returns
    -------
    PlanValidationResult with ``is_valid``, ``issues`` and a
    ``missing_required_params`` mapping for the UI to render inline
    form-widgets.
    """
    issues: List[PlanIssue] = []
    nodes = plan.get("nodes") or []
    edges = plan.get("edges") or []
    node_ids: List[str] = []
    seen_ids = set()

    if not isinstance(nodes, list) or not nodes:
        issues.append(
            PlanIssue(
                severity="error",
                code="empty_plan",
                message="Plan must contain at least one node.",
            )
        )
        return PlanValidationResult(is_valid=False, issues=issues)

    for idx, n in enumerate(nodes):
        n = _ensure_dict(n)
        if not isinstance(n, Mapping):
            issues.append(
                PlanIssue(
                    severity="error",
                    code="not_a_mapping",
                    message=f"Node #{idx} is not a mapping.",
                )
            )
            continue
        nid = n.get("id")
        if not nid:
            issues.append(
                PlanIssue(
                    severity="error",
                    code="missing_id",
                    message=f"Node #{idx} has no id.",
                    node_id=None,
                )
            )
        elif nid in seen_ids:
            issues.append(
                PlanIssue(
                    severity="error",
                    code="duplicate_id",
                    message=f"Duplicate node id '{nid}'.",
                    node_id=nid,
                )
            )
        else:
            seen_ids.add(nid)
            node_ids.append(nid)

        ntype = n.get("type")
        if not ntype:
            issues.append(
                PlanIssue(
                    severity="error",
                    code="missing_type",
                    message=f"Node '{nid or idx}' has no type.",
                    node_id=nid,
                )
            )
            continue
        schema = node_required_params(ntype)
        if schema.get("_unknown"):
            issues.append(
                PlanIssue(
                    severity="warning",
                    code="unknown_node_type",
                    message=f"Node type '{ntype}' is not in the catalog.",
                    node_id=nid,
                )
            )
            continue
        cfg = _ensure_dict(n.get("config") or {})
        missing_required_params: Dict[str, List[str]] = {}
        for req in schema["required"]:
            if req not in cfg or cfg.get(req) in (None, ""):
                missing_required_params.setdefault(nid, []).append(req)
        for nid, missing in missing_required_params.items():
            for field_name in missing:
                issues.append(
                    PlanIssue(
                        severity="error",
                        code="missing_required_param",
                        message=(
                            f"Node '{nid}' of type '{ntype}' requires "
                            f"parameter '{field_name}'."
                        ),
                        node_id=nid,
                    )
                )

    # Edge checks: endpoints must reference known node ids.
    id_set = set(node_ids)
    for idx, e in enumerate(edges):
        e = _ensure_dict(e)
        if not isinstance(e, Mapping):
            continue
        frm = e.get("from")
        to = e.get("to")
        if frm is None or to is None:
            issues.append(
                PlanIssue(
                    severity="error",
                    code="edge_missing_endpoint",
                    message=f"Edge #{idx} missing endpoint(s).",
                )
            )
            continue
        if frm not in id_set:
            issues.append(
                PlanIssue(
                    severity="error",
                    code="edge_unknown_from",
                    message=f"Edge #{idx} has unknown source '{frm}'.",
                )
            )
        if to not in id_set:
            issues.append(
                PlanIssue(
                    severity="error",
                    code="edge_unknown_to",
                    message=f"Edge #{idx} has unknown target '{to}'.",
                )
            )

    # Cycle detection via DFS.
    adjacency: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        e = _ensure_dict(e)
        if isinstance(e, Mapping):
            frm = e.get("from")
            to = e.get("to")
            if isinstance(frm, str) and isinstance(to, str) and frm in adjacency and to in adjacency:
                adjacency[frm].append(to)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in node_ids}

    def _dfs(u: str, stack: List[str]) -> Optional[List[str]]:
        color[u] = GRAY
        stack.append(u)
        for v in adjacency.get(u, []):
            if color[v] == GRAY:
                return stack + [v]
            if color[v] == WHITE:
                cyc = _dfs(v, stack)
                if cyc:
                    return cyc
        color[u] = BLACK
        stack.pop()
        return None

    for nid in list(node_ids):
        if color[nid] == WHITE:
            cycle = _dfs(nid, [])
            if cycle:
                issues.append(
                    PlanIssue(
                        severity="error",
                        code="cycle_detected",
                        message=(
                            "Cycle detected in plan edges: "
                            + " -> ".join(cycle)
                        ),
                    )
                )
                break

    return PlanValidationResult(
        is_valid=not any(i.severity == "error" for i in issues),
        issues=issues,
        missing_required_params={},
    )


# ---------------------------------------------------------------------------
# Plan diff
# ---------------------------------------------------------------------------


def _indexed_plan(plan: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for n in plan.get("nodes") or []:
        if isinstance(n, Mapping):
            nid = n.get("id")
            if isinstance(nid, str):
                by_id[nid] = _ensure_dict(n)
    return by_id


def _edge_set(plan: Mapping[str, Any]) -> set:
    s = set()
    for e in plan.get("edges") or []:
        if isinstance(e, Mapping):
            frm = e.get("from")
            to = e.get("to")
            if isinstance(frm, str) and isinstance(to, str):
                s.add((frm, to))
    return s


def diff_plans(
    base: Mapping[str, Any],
    revised: Mapping[str, Any],
) -> Dict[str, Any]:
    """Compute node-level added/removed/changed diff between two plans.

    Returns a dict with ``added``, ``removed``, ``changed`` lists of
    node ids and an ``edge_diff`` dict describing edge-level changes.
    """
    base_by_id = _indexed_plan(base)
    rev_by_id = _indexed_plan(revised)
    added = sorted(set(rev_by_id) - set(base_by_id))
    removed = sorted(set(base_by_id) - set(rev_by_id))
    changed: List[Dict[str, Any]] = []
    for nid in sorted(set(base_by_id) & set(rev_by_id)):
        if base_by_id[nid] != rev_by_id[nid]:
            changed.append(
                {
                    "id": nid,
                    "before": base_by_id[nid],
                    "after": rev_by_id[nid],
                }
            )

    base_edges = _edge_set(base)
    rev_edges = _edge_set(revised)
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "edge_diff": {
            "added": sorted(rev_edges - base_edges),
            "removed": sorted(base_edges - rev_edges),
        },
        "n_added": len(added),
        "n_removed": len(removed),
        "n_changed": len(changed),
    }


# ---------------------------------------------------------------------------
# Auto-repair loop
# ---------------------------------------------------------------------------


def autorepair_loop(
    initial_plan: Mapping[str, Any],
    planner_fn,
    *,
    max_attempts: int = 2,
) -> Dict[str, Any]:
    """Run the LLM in a bounded reflow loop until validation passes.

    ``planner_fn(plan, feedback) -> new_plan`` takes the current plan
    and the previous validation issues and returns a revised plan.
    The loop terminates when :func:`validate_plan` returns
    ``is_valid=True`` or after ``max_attempts`` iterations.
    """
    plan = dict(initial_plan)
    history: List[Dict[str, Any]] = []
    for attempt in range(int(max_attempts) + 1):
        val = validate_plan(plan)
        history.append({"attempt": attempt, "result": val.to_dict()})
        if val.is_valid:
            return {
                "final_plan": plan,
                "history": history,
                "status": "valid",
                "attempts": attempt,
            }
        feedback = {
            "issues": val.to_dict()["issues"],
            "missing_required_params": val.missing_required_params,
        }
        try:
            plan = planner_fn(plan, feedback)
        except Exception as exc:  # noqa: BLE001
            return {
                "final_plan": plan,
                "history": history,
                "status": "planner_error",
                "error": repr(exc),
                "attempts": attempt,
            }
    return {
        "final_plan": plan,
        "history": history,
        "status": "still_invalid",
        "attempts": max_attempts,
    }


# ---------------------------------------------------------------------------
# Chat guide starter
# ---------------------------------------------------------------------------


GUIDE_STARTER: Tuple[Dict[str, str], ...] = (
    {
        "key": "goal",
        "label": "Tahmin hedefiniz nedir?",
        "placeholder": "örn. müşteri kaybı, satış tahmini, anomali tespiti",
    },
    {
        "key": "data",
        "label": "Veri kaynağınız hangisi?",
        "placeholder": "örn. Snowflake, BigQuery, CSV upload",
    },
    {
        "key": "frequency",
        "label": "Pipeline ne sıklıkta çalışmalı?",
        "placeholder": "günlük / saatlik / cron / olay tetiklemeli",
    },
)


def chat_guide_starter() -> List[Dict[str, str]]:
    """Return the three-step guided starter for empty chat sessions."""
    return [dict(item) for item in GUIDE_STARTER]


__all__ = [
    "PlanIssue",
    "PlanValidationResult",
    "validate_plan",
    "node_required_params",
    "diff_plans",
    "autorepair_loop",
    "chat_guide_starter",
    "I1_PLANNER_TOOL_NAMES",
]


I1_PLANNER_TOOL_NAMES = [
    "i1_validate_plan",
    "i1_diff_plans",
    "i1_autorepair",
    "i1_chat_guide",
]
