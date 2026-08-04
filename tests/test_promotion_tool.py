"""Tests for ``ai_data_science_team.tools.promotion`` (G5 tool layer)."""

from __future__ import annotations

import ai_data_science_team.tools.promotion as g5


class TestRegisterVersion:
    def test_basic(self):
        reg, rec = g5.register_version("m", "1", input_schema=["x"], output_type="proba")
        assert rec.model_id == "m"
        assert rec.version == "1"
        assert rec.stage == "dev"
        assert "1" in reg

    def test_with_metrics(self):
        reg, rec = g5.register_version("m", "1", metrics={"auc": 0.91})
        assert rec.metrics["auc"] == 0.91


class TestValidateSignature:
    def test_match(self):
        a = g5.ModelVersionRecord(
            model_id="m", version="1", input_schema=["x", "y"], output_type="p"
        )
        b = g5.ModelVersionRecord(
            model_id="m", version="2", input_schema=["x", "y"], output_type="p"
        )
        ok, issues = g5.validate_signature(a, b)
        assert ok is True
        assert issues == []

    def test_mismatch(self):
        a = g5.ModelVersionRecord(model_id="m", version="1", input_schema=["x"], output_type="p")
        b = g5.ModelVersionRecord(
            model_id="m", version="2", input_schema=["x", "z"], output_type="c"
        )
        ok, issues = g5.validate_signature(a, b)
        assert ok is False
        assert len(issues) == 2


class TestMinMetrics:
    def test_passes(self):
        ok, issues = g5.evaluate_min_metrics({"auc": 0.9, "f1": 0.8}, {"auc": 0.85, "f1": 0.75})
        assert ok is True
        assert issues == []

    def test_fails(self):
        ok, issues = g5.evaluate_min_metrics({"auc": 0.7}, {"auc": 0.85})
        assert ok is False
        assert any("auc" in i for i in issues)

    def test_missing(self):
        ok, issues = g5.evaluate_min_metrics({}, {"auc": 0.85})
        assert ok is False


class TestRequestPromotion:
    def test_dev_to_staging_pending_approval(self):
        rec = g5.ModelVersionRecord(model_id="m", version="1", metrics={"auc": 0.9})
        out = g5.request_promotion(
            rec,
            "staging",
            reason="first",
            require_approval=True,
        )
        assert out["status"] == "pending_approval"
        assert rec.stage == "dev"  # not moved until approve()
        assert rec.audit_trail

    def test_no_approval_direct(self):
        # With require_approval=False, dev -> staging is approved
        # immediately (no HITL gate).  The version is moved by an
        # explicit approve() call; request_promotion only flips the
        # status string.
        rec = g5.ModelVersionRecord(model_id="m", version="1")
        out = g5.request_promotion(
            rec,
            "staging",
            reason="quick",
            require_approval=False,
        )
        assert out["status"] == "approved"
        # Stage is still dev; an explicit approve() moves it.
        assert rec.stage == "dev"
        # Use the request's own rec — bypass register_version to
        # avoid clobbering rec's stage field with a new dev version.
        g5.approve(rec, "staging", registry={rec.version: rec}, reason="x")
        assert rec.stage == "staging"

    def test_illegal_transition(self):
        rec = g5.ModelVersionRecord(model_id="m", version="1")
        out = g5.request_promotion(rec, "production", reason="x")
        assert out["status"] == "rejected"

    def test_min_metrics_fail(self):
        rec = g5.ModelVersionRecord(model_id="m", version="1", metrics={"auc": 0.7})
        out = g5.request_promotion(
            rec,
            "staging",
            reason="x",
            min_metrics={"auc": 0.85},
        )
        assert out["status"] == "rejected"

    def test_signature_mismatch(self):
        a = g5.ModelVersionRecord(model_id="m", version="1", input_schema=["x"], output_type="p")
        b = g5.ModelVersionRecord(model_id="m", version="2", input_schema=["y"], output_type="p")
        out = g5.request_promotion(a, "staging", reason="x", target_for_signature=b)
        assert out["status"] == "rejected"

    def test_unknown_stage(self):
        rec = g5.ModelVersionRecord(model_id="m", version="1")
        out = g5.request_promotion(rec, "galaxy", reason="x")
        assert out["status"] == "rejected"


class TestApprove:
    def test_full_flow(self):
        reg, v1 = g5.register_version("m", "1", metrics={"auc": 0.9})
        out = g5.request_promotion(v1, "staging", reason="x")
        assert out["status"] == "pending_approval"
        out = g5.approve(v1, "staging", registry=reg, reason="OK")
        assert out["status"] == "approved"
        assert v1.stage == "staging"
        assert v1.is_champion is False

    def test_to_production_archives_predecessor(self):
        reg, v1 = g5.register_version("m", "1", metrics={"auc": 0.9})
        g5.approve(v1, "staging", registry=reg, reason="x")
        g5.approve(v1, "production", registry=reg, reason="x")
        # Now v2:
        reg, v2 = g5.register_version("m", "2", metrics={"auc": 0.91}, registry=reg)
        g5.approve(v2, "staging", registry=reg, reason="x")
        g5.approve(v2, "production", registry=reg, reason="x")
        assert v1.stage == "archived"
        assert v2.is_champion is True
        assert v1.is_champion is False


class TestDemote:
    def test_production_to_staging(self):
        rec = g5.ModelVersionRecord(model_id="m", version="1", stage="production")
        out = g5.demote(rec, "staging", reason="regression")
        assert out["status"] == "approved"
        assert rec.stage == "staging"

    def test_illegal(self):
        rec = g5.ModelVersionRecord(model_id="m", version="1", stage="dev")
        out = g5.demote(rec, "production", reason="x")
        assert out["status"] == "rejected"


class TestGetVersionByStage:
    def test_pick_highest(self):
        reg, _ = g5.register_version("m", "9")
        reg, _ = g5.register_version("m", "10", registry=reg)
        # make v10 production
        reg["9"]
        v10 = reg["10"]
        g5.approve(v10, "staging", registry=reg, reason="x")
        g5.approve(v10, "production", registry=reg, reason="x")
        assert g5.get_version_by_stage(reg, "production") == "10"

    def test_empty(self):
        assert g5.get_version_by_stage({}, "production") is None


class TestMLflowAliasSync:
    def test_no_mlflow(self):
        out = g5.mlflow_alias_sync("m", "1", "champion")
        # mlflow likely not in the runtime; either ok or no_mlflow.
        assert out["status"] in {"ok", "no_mlflow"}
