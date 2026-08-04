from __future__ import annotations

"""j7_governance. Deterministic governance / approval-chain /
checklist tools. Implements J7 — risk classification, multi-step
approval chain (sequential signatures with role constraints),
checklist engine, audit-log recording, and audit-report rendering.
"""

import time  # noqa: E402, F401
import uuid  # noqa: E402, F401
from dataclasses import dataclass, field  # noqa: E402, F401
from typing import Any, Dict, List, Mapping, Optional, Sequence  # noqa: E402, F401

VALID_RISK_CLASSES = {"low", "medium", "high"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


# ----- Risk classification -------------------------------------------------


@dataclass
class RiskPolicy:
    """Required number of approvers per risk class."""

    min_approvers_low: int = 1
    min_approvers_medium: int = 1
    min_approvers_high: int = 2


@dataclass
class RiskAssignment:
    model_id: str
    risk_class: str
    assigned_by: str
    rationale: str
    assigned_at: float


def assign_risk(
    *,
    model_id: str,
    risk_class: str,
    assigned_by: str,
    rationale: str = "",
) -> RiskAssignment:
    if risk_class not in VALID_RISK_CLASSES:
        raise ValueError(f"risk_class must be one of {sorted(VALID_RISK_CLASSES)}")
    return RiskAssignment(
        model_id=model_id,
        risk_class=risk_class,
        assigned_by=assigned_by,
        rationale=rationale,
        assigned_at=_now(),
    )


def required_approvers(risk_class: str, policy: RiskPolicy) -> int:
    if risk_class == "low":
        return policy.min_approvers_low
    if risk_class == "medium":
        return policy.min_approvers_medium
    if risk_class == "high":
        return policy.min_approvers_high
    raise ValueError(f"unknown risk_class: {risk_class}")


# ----- Approval chain ------------------------------------------------------


@dataclass
class ApprovalStep:
    step_id: str
    required_role: str
    approver_id: Optional[str] = None
    approved_at: Optional[float] = None
    note: str = ""


@dataclass
class ApprovalChain:
    chain_id: str
    model_id: str
    steps: List[ApprovalStep]
    started_at: float

    def is_complete(self) -> bool:
        return all(s.approver_id is not None for s in self.steps)


def start_approval_chain(
    *,
    model_id: str,
    required_steps: Sequence[Mapping[str, Any]],
    chain_id: Optional[str] = None,
) -> ApprovalChain:
    if not required_steps:
        raise ValueError("required_steps must be non-empty")
    steps = [
        ApprovalStep(
            step_id=str(s.get("step_id") or _new_id()),
            required_role=str(s["required_role"]),
        )
        for s in required_steps
    ]
    return ApprovalChain(
        chain_id=chain_id or _new_id(),
        model_id=model_id,
        steps=steps,
        started_at=_now(),
    )


def approve_step(
    chain: ApprovalChain,
    *,
    step_id: str,
    approver_id: str,
    approver_role: str,
    note: str = "",
) -> None:
    """Approve a step. Enforces: (1) step must exist, (2) role
    must match required_role, (3) step not already approved."""
    target = next((s for s in chain.steps if s.step_id == step_id), None)
    if target is None:
        raise KeyError(f"step_id not found: {step_id}")
    if target.approver_id is not None:
        raise ValueError(f"step already approved by {target.approver_id}")
    if target.required_role != approver_role:
        raise ValueError(
            f"approver_role {approver_role!r} does not match required_role {target.required_role!r}"
        )
    target.approver_id = approver_id
    target.approved_at = _now()
    target.note = note


def chain_progress(chain: ApprovalChain) -> Dict[str, Any]:
    n_total = len(chain.steps)
    n_done = sum(1 for s in chain.steps if s.approver_id is not None)
    return {
        "chain_id": chain.chain_id,
        "model_id": chain.model_id,
        "steps_total": n_total,
        "steps_done": n_done,
        "complete": n_done == n_total,
    }


# ----- Checklist engine ----------------------------------------------------


@dataclass
class ChecklistItem:
    check_id: str
    description: str
    required: bool = True
    passed: bool = False
    evidence: str = ""


@dataclass
class ChecklistEvaluation:
    model_id: str
    items: List[ChecklistItem]
    required_pass: int
    required_failed: int
    optional_passed: int
    optional_failed: int
    passed: bool

    @property
    def failed_required_ids(self) -> List[str]:
        return [it.check_id for it in self.items if it.required and not it.passed]


def build_checklist(
    *,
    model_id: str,
    items: Sequence[Mapping[str, Any]],
) -> List[ChecklistItem]:
    return [
        ChecklistItem(
            check_id=str(it["check_id"]),
            description=str(it.get("description", "")),
            required=bool(it.get("required", True)),
            passed=bool(it.get("passed", False)),
            evidence=str(it.get("evidence", "")),
        )
        for it in items
    ]


def evaluate_checklist(
    *,
    model_id: str,
    items: Sequence[ChecklistItem],
) -> ChecklistEvaluation:
    required_pass = sum(1 for it in items if it.required and it.passed)
    required_failed = sum(1 for it in items if it.required and not it.passed)
    optional_passed = sum(1 for it in items if not it.required and it.passed)
    optional_failed = sum(1 for it in items if not it.required and not it.passed)
    return ChecklistEvaluation(
        model_id=model_id,
        items=list(items),
        required_pass=required_pass,
        required_failed=required_failed,
        optional_passed=optional_passed,
        optional_failed=optional_failed,
        passed=(required_failed == 0),
    )


# ----- Audit log -----------------------------------------------------------


@dataclass
class AuditEntry:
    timestamp: float
    actor: str
    action: str
    target: str
    detail: str = ""


@dataclass
class AuditLog:
    entries: List[AuditEntry] = field(default_factory=list)

    def record(self, *, actor: str, action: str, target: str, detail: str = "") -> AuditEntry:
        e = AuditEntry(
            timestamp=_now(),
            actor=actor,
            action=action,
            target=target,
            detail=detail,
        )
        self.entries.append(e)
        return e

    def filter(
        self,
        *,
        action: Optional[str] = None,
        target: Optional[str] = None,
    ) -> List[AuditEntry]:
        out = list(self.entries)
        if action is not None:
            out = [e for e in out if e.action == action]
        if target is not None:
            out = [e for e in out if e.target == target]
        return out


def render_audit_report(
    log: AuditLog,
    *,
    model_id: str,
) -> Dict[str, Any]:
    entries = log.filter(target=model_id)
    return {
        "model_id": model_id,
        "n_entries": len(entries),
        "entries": [
            {
                "timestamp": e.timestamp,
                "actor": e.actor,
                "action": e.action,
                "detail": e.detail,
            }
            for e in entries
        ],
    }


# ----- Gate (combining risk + chain + checklist) --------------------------


def promotion_gate(
    *,
    risk: RiskAssignment,
    chain: ApprovalChain,
    checklist: ChecklistEvaluation,
    policy: RiskPolicy,
    audit: AuditLog,
) -> Dict[str, Any]:
    """Return whether promotion to prod is allowed, with reasons."""
    audit.record(
        actor="j7_governance",
        action="promotion.evaluate",
        target=risk.model_id,
        detail=f"risk={risk.risk_class}",
    )
    reasons: List[str] = []
    need = required_approvers(risk.risk_class, policy)
    n_approved = sum(1 for s in chain.steps if s.approver_id is not None)
    if n_approved < need:
        reasons.append(f"approval chain incomplete: {n_approved}/{need} required")
    if not checklist.passed:
        reasons.append(f"checklist failed: {checklist.failed_required_ids}")
    allowed = len(reasons) == 0
    if allowed:
        audit.record(
            actor="j7_governance",
            action="promotion.allowed",
            target=risk.model_id,
        )
    return {
        "model_id": risk.model_id,
        "allowed": allowed,
        "reasons": reasons,
    }
