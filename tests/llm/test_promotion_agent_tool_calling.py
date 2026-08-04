"""GERÇEK promotion_agent tool doğrulaması (PM kararı: stub test yok).

Kapsam: ai_data_science_team/agents/promotion_agent.py — 8 tool.

Strateji:
- PURE (model-driven): ``register_version``, ``evaluate_min_metrics``,
  ``mlflow_alias_sync`` model tarafından çağrılır.
- STATEFUL: ``validate_signature``, ``request_promotion``, ``approve``,
  ``demote``, ``get_version_by_stage`` tools/promotion.py doğrudan çağrılır;
  gerçek ModelVersionRecord instance'ları test'te yaratılır.

Mock YOK. Stub YOK. CallableModel YOK. Tool başarısız olursa FAIL.
"""

from __future__ import annotations

import pytest

from ai_data_science_team.agents.promotion_agent import (
    evaluate_min_metrics_wrapped,
    mlflow_alias_sync_wrapped,
    register_version_wrapped,
)
from ai_data_science_team.tools.promotion import (
    ModelVersionRecord,
    approve,
    demote,
    get_version_by_stage,
    request_promotion,
    validate_signature,
)
from tests.llm._driver import _assert_result, _drive_tool_call

pytestmark = pytest.mark.llm


def _fresh_record(
    model_id: str = "model-demo",
    version: str = "1.0.0",
    input_schema=None,
    output_type: str = "scalar",
    metrics=None,
) -> ModelVersionRecord:
    """Test için taze, izole ModelVersionRecord — gerçek dataclass."""
    return ModelVersionRecord(
        model_id=model_id,
        version=version,
        stage="dev",
        input_schema=list(input_schema) if input_schema else None,
        output_type=output_type,
        metrics=dict(metrics or {}),
    )


# ---------------------------------------------------------------------------
# 1. PURE: model-driven doğrulanabilen 3 tool
# ---------------------------------------------------------------------------


def test_register_version_real(llm_or_skip, llm_model):
    tool = register_version_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "register_version_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo', version='1.0.0' ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_evaluate_min_metrics_real(llm_or_skip, llm_model):
    tool = evaluate_min_metrics_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "evaluate_min_metrics_wrapped tool'unu TEK çağrı ile çağır; metrics={'accuracy':0.91}, required={'accuracy':0.90} ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


def test_mlflow_alias_sync_real(llm_or_skip, llm_model):
    tool = mlflow_alias_sync_wrapped
    content, artifact = _assert_result(
        _drive_tool_call(
            llm_model,
            tool,
            "mlflow_alias_sync_wrapped tool'unu TEK çağrı ile çağır; model_id='model-demo', version='1.0.0', alias='champion', registry_uri=None ver.",  # noqa: E501
        ),
        tool.name,
    )
    assert content
    assert artifact is not None


# ---------------------------------------------------------------------------
# 2. STATEFUL: ModelVersionRecord / registry gerektiren tool'lar
# ---------------------------------------------------------------------------
# ModelVersionRecord dataclass Pydantic JSON-serializable olmadığı için
# model-driven harness'te çalışmaz. tools/promotion.py doğrudan çağrılır;
# gerçek dataclass instance'ları test'te yaratılır.
# ---------------------------------------------------------------------------


def test_validate_signature_real():
    """validate_signature(candidate, target) → (ok, issues).

    Aynı input_schema ve output_type için ok=True, farklı output_type için
    issues listesinde 'output_type mismatch' olmalı.
    """
    cand = _fresh_record(input_schema=["a", "b"], output_type="scalar")
    tgt = _fresh_record(input_schema=["a", "b"], output_type="scalar")
    ok, issues = validate_signature(candidate=cand, target=tgt)
    assert ok is True
    assert issues == []

    cand2 = _fresh_record(input_schema=["a", "b"], output_type="prob")
    ok2, issues2 = validate_signature(candidate=cand2, target=tgt)
    assert ok2 is False
    assert any("output_type mismatch" in i for i in issues2)


def test_request_promotion_real():
    """request_promotion(record, to_stage, *, reason, ...) → {status, ...}.

    dev → staging (require_approval=True) → status='pending_approval'.
    dev → staging (require_approval=False) → status='approved'.
    """
    rec = _fresh_record(metrics={"accuracy": 0.95})
    out = request_promotion(record=rec, to_stage="staging", reason="baseline")
    assert out["status"] == "pending_approval"
    assert out["to_stage"] == "staging"
    assert rec.stage == "dev"  # henüz approve edilmedi

    out2 = request_promotion(record=rec, to_stage="staging", reason="auto", require_approval=False)
    assert out2["status"] == "approved"


def test_approve_real():
    """approve(record, to_stage, *, ...) → {status, archived, is_champion, ...}.

    staging → production + registry var + record champion olur; önceki
    production kaydı auto_archive edilir.
    """
    rec_v1 = _fresh_record(version="1.0.0")
    rec_v1.stage = "production"
    rec_v1.is_champion = True

    rec_v2 = _fresh_record(version="2.0.0")
    rec_v2.stage = "staging"

    registry = {"1.0.0": rec_v1, "2.0.0": rec_v2}
    out = approve(record=rec_v2, to_stage="production", registry=registry)
    assert out["status"] == "approved"
    assert out["to_stage"] == "production"
    assert out["is_champion"] is True
    assert rec_v2.stage == "production"
    # Önceki production auto-archived
    assert rec_v1.stage == "archived"
    assert "1.0.0" in out["archived"]


def test_demote_real():
    """demote(record, to_stage, *, ...) → rejected veya approve çıktısı."""
    rec = _fresh_record(version="3.0.0")
    rec.stage = "production"
    out = demote(record=rec, to_stage="staging", reason="rollback")
    assert out["status"] == "approved"
    assert out["to_stage"] == "staging"
    assert rec.stage == "staging"

    # illegal transition: dev → production demote edilemez
    # (VALID_TRANSITIONS['dev'] = ['staging', 'archived'])
    rec2 = _fresh_record(version="3.0.1")
    rec2.stage = "dev"
    out2 = demote(record=rec2, to_stage="production", reason="x")
    assert out2["status"] == "rejected"


def test_get_version_by_stage_real():
    """get_version_by_stage(registry, stage) → version key veya None.

    Sayısal versiyonlar lexicographic değil integer karşılaştırmasıyla
    sıralanır; v10 > v9 (tüm versiyonlar int olarak parse edilebilir).
    """
    rec1 = _fresh_record(version="1")
    rec1.stage = "production"
    rec9 = _fresh_record(version="9")
    rec9.stage = "production"
    rec10 = _fresh_record(version="10")
    rec10.stage = "production"
    registry = {"1": rec1, "9": rec9, "10": rec10}

    out = get_version_by_stage(registry=registry, stage="production")
    assert out == "10"

    # Boş stage
    assert get_version_by_stage(registry=registry, stage="dev") is None
