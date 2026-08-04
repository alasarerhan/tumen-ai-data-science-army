"""GERÇEK test governance_agent tool doğrulaması (PM kararı: skip yok).

Kapsam: ai_data_science_team/agents/governance_agent.py — 9 tool.

Strateji:
Bu agent'ın TÜM 9 tool'u stateful kategorisindedir. Pydantic/dataclass
objeler (``RiskPolicy``, ``ApprovalChain``, ``AuditLog``,
``RiskAssignment``, ``ChecklistEvaluation``) test fonksiyonlarında
gerçekten yaratılır ve **underlying tool** doğrudan çağrılır.

PURE tool yoktur, dolayısıyla model-driven harness'a gerek yoktur.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.tools.governance import (
    ApprovalChain,
    AuditLog,
    ChecklistItem,
    RiskAssignment,
    RiskPolicy,
    approve_step,
    assign_risk,
    build_checklist,
    chain_progress,
    evaluate_checklist,
    promotion_gate,
    render_audit_report,
    required_approvers,
    start_approval_chain,
)

pytestmark = pytest.mark.llm


# ---------------------------------------------------------------------------
# Yardımcılar: gerçek Pydantic/dataclass state nesneleri
# ---------------------------------------------------------------------------

def _policy() -> RiskPolicy:
    return RiskPolicy()


def _risk(level: str = "low") -> RiskAssignment:
    return assign_risk(
        model_id="model-1",
        risk_class=level,
        assigned_by="alice",
        rationale="test",
    )


def _chain_complete() -> ApprovalChain:
    """Tek-step, onaylanmış ApprovalChain."""
    chain = start_approval_chain(
        model_id="model-1",
        required_steps=[{"required_role": "approver"}],
    )
    approve_step(
        chain,
        step_id=chain.steps[0].step_id,
        approver_id="u1",
        approver_role="approver",
        note="ok",
    )
    return chain


def _chain_partial() -> ApprovalChain:
    """Onaylanmamış ApprovalChain."""
    return start_approval_chain(
        model_id="model-1",
        required_steps=[{"required_role": "approver"}],
    )


def _checklist(passed: bool = True) -> tuple[list[ChecklistItem], object]:
    items = build_checklist(
        model_id="model-1",
        items=[{"check_id": "c1", "passed": passed, "required": True}],
    )
    return items, evaluate_checklist(model_id="model-1", items=items)


def _audit_with(model_id: str, action: str = "promotion.evaluate") -> AuditLog:
    log = AuditLog()
    log.record(actor="j7", action=action, target=model_id, detail="x")
    return log


# ---------------------------------------------------------------------------
# 9 STATEFUL tool'un gerçek testleri
# ---------------------------------------------------------------------------

def test_assign_risk_real():
    """assign_risk: RiskAssignment döner."""
    out = assign_risk(
        model_id="m1", risk_class="high", assigned_by="alice",
        rationale="financial impact",
    )
    assert isinstance(out, RiskAssignment)
    assert out.model_id == "m1"
    assert out.risk_class == "high"
    assert out.assigned_by == "alice"


def test_required_approvers_real():
    """required_approvers: RiskPolicy'den sayı."""
    policy = RiskPolicy()
    assert required_approvers("low", policy) == policy.min_approvers_low
    assert required_approvers("medium", policy) == policy.min_approvers_medium
    assert required_approvers("high", policy) == policy.min_approvers_high


def test_start_approval_chain_real():
    """start_approval_chain: ApprovalChain + ApprovalStep listesi."""
    chain = start_approval_chain(
        model_id="m1",
        required_steps=[
            {"required_role": "reviewer"},
            {"required_role": "approver"},
        ],
    )
    assert isinstance(chain, ApprovalChain)
    assert chain.model_id == "m1"
    assert len(chain.steps) == 2
    assert chain.steps[0].required_role == "reviewer"
    assert chain.steps[0].approver_id is None


def test_approve_step_real():
    """approve_step: zincirdeki step'i onaylar."""
    chain = start_approval_chain(
        model_id="m1",
        required_steps=[{"required_role": "approver"}],
    )
    approve_step(
        chain,
        step_id=chain.steps[0].step_id,
        approver_id="user-1",
        approver_role="approver",
    )
    assert chain.steps[0].approver_id == "user-1"
    assert chain.steps[0].approved_at is not None
    assert chain.is_complete() is True


def test_chain_progress_real():
    """chain_progress: tamamlanma yüzdesi."""
    chain = _chain_partial()
    prog = chain_progress(chain)
    assert prog["steps_total"] == 1
    assert prog["steps_done"] == 0
    assert prog["complete"] is False
    chain2 = _chain_complete()
    prog2 = chain_progress(chain2)
    assert prog2["steps_done"] == 1
    assert prog2["complete"] is True


def test_build_checklist_real():
    """build_checklist: ChecklistItem listesi."""
    items = build_checklist(
        model_id="m1",
        items=[
            {"check_id": "c1", "description": "bias", "passed": True},
            {"check_id": "c2", "description": "drift", "passed": False, "required": True},
        ],
    )
    assert len(items) == 2
    assert items[0].check_id == "c1"
    assert items[0].passed is True
    assert items[1].required is True


def test_evaluate_checklist_real():
    """evaluate_checklist: required_failed + passed."""
    items, eval_result = _checklist(passed=True)
    assert eval_result.passed is True
    assert eval_result.required_failed == 0
    items2, eval2 = _checklist(passed=False)
    assert eval2.passed is False
    assert eval2.required_failed == 1
    assert eval2.failed_required_ids == ["c1"]


def test_render_audit_report_real():
    """render_audit_report: model_id filtresi + entries listesi."""
    log = _audit_with(model_id="m1", action="promotion.evaluate")
    log.record(actor="bob", action="notify", target="m1", detail="email")
    out = render_audit_report(log, model_id="m1")
    assert out["model_id"] == "m1"
    assert out["n_entries"] == 2
    assert all("actor" in e for e in out["entries"])


def test_promotion_gate_real():
    """promotion_gate: tüm bileşenler uygun → allowed=True."""
    risk = _risk("low")
    chain = _chain_complete()
    items, checklist = _checklist(passed=True)
    audit = AuditLog()
    out = promotion_gate(
        risk=risk, chain=chain, checklist=checklist,
        policy=_policy(), audit=audit,
    )
    assert out["model_id"] == "model-1"
    assert out["allowed"] is True
    assert out["reasons"] == []
    # Chain eksik → reasons uyarısı
    out2 = promotion_gate(
        risk=risk, chain=_chain_partial(), checklist=checklist,
        policy=_policy(), audit=audit,
    )
    assert out2["allowed"] is False
    assert any("approval chain" in r for r in out2["reasons"])
