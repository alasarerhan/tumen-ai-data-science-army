"""Tests for J7 Governance tool."""
from __future__ import annotations

import pytest

import ai_data_science_team.tools.j7_governance as j7


class TestAssignRisk:
    def test_valid_classes(self):
        for cls in ("low", "medium", "high"):
            r = j7.assign_risk(
                model_id="m1", risk_class=cls,
                assigned_by="alice",
            )
            assert r.risk_class == cls
            assert r.model_id == "m1"

    def test_invalid_class_raises(self):
        with pytest.raises(ValueError):
            j7.assign_risk(model_id="m1", risk_class="extreme",
                            assigned_by="alice")


class TestApprovalChain:
    def test_start_chain(self):
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[
                {"required_role": "data_scientist"},
                {"required_role": "risk_officer"},
            ],
        )
        assert len(chain.steps) == 2
        assert chain.is_complete() is False

    def test_approve_step(self):
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        step = chain.steps[0]
        j7.approve_step(
            chain, step_id=step.step_id,
            approver_id="u1", approver_role="data_scientist",
        )
        assert chain.is_complete() is True

    def test_role_mismatch_raises(self):
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        with pytest.raises(ValueError):
            j7.approve_step(
                chain, step_id=chain.steps[0].step_id,
                approver_id="u1", approver_role="admin",
            )

    def test_double_approval_raises(self):
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        sid = chain.steps[0].step_id
        j7.approve_step(chain, step_id=sid, approver_id="u1",
                         approver_role="data_scientist")
        with pytest.raises(ValueError):
            j7.approve_step(chain, step_id=sid, approver_id="u2",
                             approver_role="data_scientist")

    def test_unknown_step_raises(self):
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        with pytest.raises(KeyError):
            j7.approve_step(chain, step_id="nope",
                             approver_id="u1",
                             approver_role="data_scientist")

    def test_chain_progress(self):
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[
                {"required_role": "data_scientist"},
                {"required_role": "risk_officer"},
            ],
        )
        prog = j7.chain_progress(chain)
        assert prog["steps_total"] == 2
        assert prog["steps_done"] == 0
        assert prog["complete"] is False
        j7.approve_step(chain, step_id=chain.steps[0].step_id,
                         approver_id="u1",
                         approver_role="data_scientist")
        prog = j7.chain_progress(chain)
        assert prog["steps_done"] == 1

    def test_empty_steps_raises(self):
        with pytest.raises(ValueError):
            j7.start_approval_chain(model_id="m1", required_steps=[])


class TestChecklist:
    def test_all_required_pass(self):
        items = j7.build_checklist(
            model_id="m1",
            items=[
                {"check_id": "c1", "passed": True},
                {"check_id": "c2", "passed": True},
            ],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        assert ev.passed is True
        assert ev.required_failed == 0

    def test_one_required_fails(self):
        items = j7.build_checklist(
            model_id="m1",
            items=[
                {"check_id": "c1", "passed": True},
                {"check_id": "c2", "passed": False},
            ],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        assert ev.passed is False
        assert "c2" in ev.failed_required_ids

    def test_optional_does_not_block(self):
        items = j7.build_checklist(
            model_id="m1",
            items=[
                {"check_id": "c1", "required": True, "passed": True},
                {"check_id": "c2", "required": False, "passed": False},
            ],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        assert ev.passed is True
        assert ev.optional_failed == 1


class TestAuditLog:
    def test_record_and_filter(self):
        log = j7.AuditLog()
        log.record(actor="alice", action="promote",
                    target="m1", detail="to prod")
        log.record(actor="bob", action="rollback",
                    target="m1", detail="alerts")
        log.record(actor="alice", action="promote",
                    target="m2", detail="")
        assert len(log.entries) == 3
        assert len(log.filter(action="promote")) == 2
        assert len(log.filter(target="m1")) == 2
        assert len(log.filter(action="rollback", target="m1")) == 1

    def test_render_report(self):
        log = j7.AuditLog()
        log.record(actor="alice", action="promote",
                    target="m1", detail="x")
        log.record(actor="bob", action="other",
                    target="m2", detail="y")
        rep = j7.render_audit_report(log, model_id="m1")
        assert rep["n_entries"] == 1
        assert rep["entries"][0]["actor"] == "alice"


class TestPromotionGate:
    def test_low_risk_one_approver_allowed(self):
        policy = j7.RiskPolicy()
        risk = j7.assign_risk(model_id="m1", risk_class="low",
                               assigned_by="alice")
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        j7.approve_step(chain, step_id=chain.steps[0].step_id,
                         approver_id="u1",
                         approver_role="data_scientist")
        items = j7.build_checklist(
            model_id="m1",
            items=[{"check_id": "c1", "passed": True}],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        audit = j7.AuditLog()
        result = j7.promotion_gate(
            risk=risk, chain=chain, checklist=ev,
            policy=policy, audit=audit,
        )
        assert result["allowed"] is True
        assert result["reasons"] == []

    def test_high_risk_needs_two_approvers(self):
        policy = j7.RiskPolicy()
        risk = j7.assign_risk(model_id="m1", risk_class="high",
                               assigned_by="alice")
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[
                {"required_role": "data_scientist"},
                {"required_role": "risk_officer"},
            ],
        )
        # only one approver
        j7.approve_step(chain, step_id=chain.steps[0].step_id,
                         approver_id="u1",
                         approver_role="data_scientist")
        items = j7.build_checklist(
            model_id="m1",
            items=[{"check_id": "c1", "passed": True}],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        audit = j7.AuditLog()
        result = j7.promotion_gate(
            risk=risk, chain=chain, checklist=ev,
            policy=policy, audit=audit,
        )
        assert result["allowed"] is False
        assert any("approval chain" in r for r in result["reasons"])

    def test_checklist_failure_blocks(self):
        policy = j7.RiskPolicy()
        risk = j7.assign_risk(model_id="m1", risk_class="low",
                               assigned_by="alice")
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        j7.approve_step(chain, step_id=chain.steps[0].step_id,
                         approver_id="u1",
                         approver_role="data_scientist")
        items = j7.build_checklist(
            model_id="m1",
            items=[{"check_id": "c1", "passed": False}],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        audit = j7.AuditLog()
        result = j7.promotion_gate(
            risk=risk, chain=chain, checklist=ev,
            policy=policy, audit=audit,
        )
        assert result["allowed"] is False
        assert any("checklist" in r for r in result["reasons"])

    def test_audit_log_records_evaluation(self):
        policy = j7.RiskPolicy()
        risk = j7.assign_risk(model_id="m1", risk_class="low",
                               assigned_by="alice")
        chain = j7.start_approval_chain(
            model_id="m1",
            required_steps=[{"required_role": "data_scientist"}],
        )
        items = j7.build_checklist(
            model_id="m1", items=[{"check_id": "c1", "passed": True}],
        )
        ev = j7.evaluate_checklist(model_id="m1", items=items)
        audit = j7.AuditLog()
        j7.promotion_gate(
            risk=risk, chain=chain, checklist=ev,
            policy=policy, audit=audit,
        )
        assert any(
            e.action == "promotion.evaluate" for e in audit.entries
        )

