from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.models import AgentExecutionTrace, Artifact, WorkflowNodeExecution
from platform_api.db.session import get_db
from platform_api.main import create_app
from platform_api.services.agent_execution_trace_service import agent_execution_trace_to_dict
from platform_api.services.workflow_ir_service import validate_workflow_ir_v2
from platform_api.services.run_service import create_workflow_run_record
from platform_api.services.workflow_node_catalog_service import list_supported_node_types
from platform_api.services.workflow_node_executor_service import NodeExecutionContext, get_default_node_executors
from platform_api.services.workflow_service import create_workflow_spec_version
from platform_api.core.config import settings
from platform_api.workers.workflow_worker import WorkflowWorker


def _valid_ir_v2_spec() -> dict:
    return {
        "version": "2.0.0",
        "ir_version": "2.0",
        "name": "churn-model-workflow",
        "description": "Profile, clean, train, evaluate, and report.",
        "triggers": [{"id": "trigger.manual", "type": "manual.trigger", "config": {}}],
        "inputs": [{"name": "dataset", "artifact_type": "dataset", "source": "run.input_artifact_ids"}],
        "nodes": [
            {"id": "profile", "type": "dataset.profile", "label": "Profile", "inputs": [], "outputs": []},
            {"id": "clean", "type": "data.clean", "label": "Clean", "inputs": [], "outputs": []},
            {"id": "features", "type": "feature.engineer", "label": "Features", "inputs": [], "outputs": []},
            {"id": "train", "type": "model.train", "label": "Train", "inputs": [], "outputs": []},
            {"id": "evaluate", "type": "model.evaluate", "label": "Evaluate", "inputs": [], "outputs": []},
            {"id": "report", "type": "report.generate", "label": "Report", "inputs": [], "outputs": []},
        ],
        "edges": [
            {"id": "e1", "source": "profile", "target": "clean"},
            {"id": "e2", "source": "clean", "target": "features"},
            {"id": "e3", "source": "features", "target": "train"},
            {"id": "e4", "source": "train", "target": "evaluate"},
            {"id": "e5", "source": "evaluate", "target": "report"},
        ],
        "graph": {
            "nodes": [
                {"id": "profile", "label": "Profile", "kind": "data", "agent": "DataLoaderToolsAgent", "position": {"x": 0, "y": 0}},
                {"id": "clean", "label": "Clean", "kind": "data", "agent": "DataCleaningAgent", "position": {"x": 220, "y": 0}},
                {"id": "features", "label": "Features", "kind": "ml", "agent": "FeatureEngineeringAgent", "position": {"x": 440, "y": 0}},
                {"id": "train", "label": "Train", "kind": "ml", "agent": "H2OMLAgent", "position": {"x": 660, "y": 0}},
                {"id": "evaluate", "label": "Evaluate", "kind": "analysis", "agent": "EDAToolsAgent", "position": {"x": 880, "y": 0}},
                {"id": "report", "label": "Report", "kind": "strategic", "agent": "NarrativeAgent", "position": {"x": 1100, "y": 0}},
            ],
            "edges": [
                {"id": "e1", "source": "profile", "target": "clean"},
                {"id": "e2", "source": "clean", "target": "features"},
                {"id": "e3", "source": "features", "target": "train"},
                {"id": "e4", "source": "train", "target": "evaluate"},
                {"id": "e5", "source": "evaluate", "target": "report"},
            ],
        },
    }


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def admin_client(app, seeded_db):
    user = seeded_db["user_admin"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal():
        return principal

    def _db():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, seeded_db
    app.dependency_overrides.clear()


def test_workflow_ir_v2_validation_catches_cycles_and_missing_inputs():
    spec = _valid_ir_v2_spec()
    spec["edges"].append({"id": "cycle", "source": "features", "target": "clean"})
    spec["inputs"] = []

    result = validate_workflow_ir_v2(spec)

    codes = {item["code"] for item in result["errors"]}
    assert "cycle_detected" in codes
    assert "missing_required_input" in codes


def test_node_catalog_endpoint_exposes_ds_mle_contracts(admin_client):
    client, sdb = admin_client
    ws_id = str(sdb["workspace"].id)

    response = client.get(f"/v1/workflow-node-types?workspace_id={ws_id}")

    assert response.status_code == 200
    types = {item["type"] for item in response.json()["items"]}
    assert {"dataset.profile", "data.clean", "feature.engineer", "model.train", "model.evaluate", "report.generate", "approval.wait", "artifact.export"}.issubset(types)


def test_run_with_workflow_spec_creates_node_execution_state(admin_client):
    client, sdb = admin_client
    db = sdb["db"]
    workspace = sdb["workspace"]
    user = sdb["user_admin"]
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        workflow = create_workflow_spec_version(
            db,
            workspace_id=str(workspace.id),
            user_id=user.id,
            name="churn-model-workflow",
            spec=_valid_ir_v2_spec(),
            publish=True,
        )
    db.commit()

    with patch("platform_api.routes.runs.create_orchestration_run_id", new=AsyncMock(return_value="prefect-ir-v2-run")):
        response = client.post(
            f"/v1/runs?workspace_id={workspace.id}",
            json={
                "workspace_id": str(workspace.id),
                "flow_key": "churn-model-workflow",
                "workflow_spec_id": str(workflow.id),
                "workflow_version": workflow.version,
                "trigger_type": "manual",
                "input_artifact_ids": ["dataset-artifact-1"],
                "parameters": {"business_goal": "reduce churn"},
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["workflow_spec_id"] == str(workflow.id)
    assert body["trigger_type"] == "manual"
    nodes = client.get(f"/v1/runs/{body['id']}/nodes?workspace_id={workspace.id}")
    assert nodes.status_code == 200
    assert [item["node_id"] for item in nodes.json()["items"]] == ["profile", "clean", "features", "train", "evaluate", "report"]


def test_retry_failed_node_and_resume_run(admin_client):
    client, sdb = admin_client
    db = sdb["db"]
    workspace = sdb["workspace"]
    user = sdb["user_admin"]
    with patch("platform_api.services.workflow_service.enforce_tenant_write_quota"):
        workflow = create_workflow_spec_version(
            db,
            workspace_id=str(workspace.id),
            user_id=user.id,
            name="retry-workflow",
            spec=_valid_ir_v2_spec(),
            publish=True,
        )
    db.commit()

    with patch("platform_api.routes.runs.create_orchestration_run_id", new=AsyncMock(return_value="prefect-retry-run")):
        run = client.post(
            f"/v1/runs?workspace_id={workspace.id}",
            json={"workspace_id": str(workspace.id), "flow_key": "retry-workflow", "workflow_spec_id": str(workflow.id)},
        ).json()

    node = db.query(WorkflowNodeExecution).filter_by(workflow_run_id=uuid.UUID(run["id"]), node_id="profile").one()
    node.status = "failed"
    node.error = "profile failed"
    db.add(node)
    db.commit()

    retry = client.post(
        f"/v1/runs/{run['id']}/nodes/profile/retry?workspace_id={workspace.id}",
        json={"workspace_id": str(workspace.id)},
    )

    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "queued"
    assert retry.json()["retry_count"] == 1

    node.status = "failed"
    node.error = "profile failed again"
    db.add(node)
    db.commit()
    resumed = client.post(f"/v1/runs/{run['id']}/resume?workspace_id={workspace.id}", json={"workspace_id": str(workspace.id)})

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["resumed_nodes"][0]["node_id"] == "profile"


def test_worker_startup_smoke_without_queue(monkeypatch):
    monkeypatch.setattr(settings, "workflow_queue_redis_url", "")
    monkeypatch.setattr(settings, "agent_cache_redis_url", "")

    result = WorkflowWorker().run_once()

    assert result == {"processed": False, "reason": "workflow_queue_not_configured"}


def test_default_executor_registry_covers_public_node_catalog():
    executors = get_default_node_executors()

    assert list_supported_node_types().issubset(executors.keys())


def test_dataset_profile_executor_reads_dataset_and_writes_profile(seeded_db, tmp_path, monkeypatch):
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    source_path = upload_dir / "source.csv"
    source_path.write_text("target,value\nyes,1\nno,2\n", encoding="utf-8")
    monkeypatch.setattr(settings, "artifact_storage_backend", "local")
    monkeypatch.setattr(settings, "artifact_storage_local_dir", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "chat_upload_dir", str(upload_dir))

    run = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key="profile-test",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex}",
        parameters={},
        input_artifact_ids=[],
    )
    source = Artifact(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="dataset",
        uri=str(source_path),
        created_by_user_id=user.id,
    )
    db.add(source)
    db.flush()
    run.input_artifact_ids_json = json.dumps([str(source.id)])
    node = WorkflowNodeExecution(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        node_id="profile",
        node_type="dataset.profile",
        execution_index=0,
        status="queued",
        inputs_json=json.dumps({"config": {"sample_rows": 2}}),
        logs_json="[]",
    )
    db.add(node)
    db.flush()

    result = get_default_node_executors()["dataset.profile"](NodeExecutionContext(db=db, run=run, node=node))

    assert result["outputs"]["row_count"] == 2
    assert result["outputs"]["column_count"] == 2
    profile_path = result["artifacts"][0]["uri"]
    assert "workflow-runs" in profile_path
    assert (tmp_path / "artifacts" / "workflow-runs" / str(run.id) / "profile" / "profile.json").exists()


def test_worker_records_safe_agent_execution_trace(admin_client):
    client, sdb = admin_client
    db = sdb["db"]
    workspace = sdb["workspace"]
    user = sdb["user_admin"]
    run = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key="trace-test",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex}",
        parameters={},
        input_artifact_ids=[],
    )
    node = WorkflowNodeExecution(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        node_id="agent-step",
        node_type="custom.agent",
        execution_index=0,
        status="queued",
        inputs_json=json.dumps({"config": {"instruction": "summarize", "password": "do-not-store"}, "api_token": "secret"}),
        logs_json="[]",
    )
    db.add(node)
    db.flush()

    def _executor(ctx: NodeExecutionContext) -> dict:
        return {
            "outputs": {
                "metric": 0.91,
                "secret_token": "do-not-store",
                "tool_calls": [{"name": "sql.query", "args": {"query": "select 1", "password": "do-not-store"}}],
                "token_usage": {"prompt_tokens": 120, "completion_tokens": 30, "api_key": "do-not-store"},
                "cost_summary": {"usd": 0.04, "credential": "do-not-store"},
                "evaluation_summary": {"auc": 0.91},
                "version_metadata": {"agent_version": "m22.1", "secret": "do-not-store"},
            },
            "logs": ["done"],
        }

    status = WorkflowWorker(node_executors={"custom.agent": _executor})._execute_node(db, run, node)
    db.commit()

    assert status == "succeeded"
    trace = db.query(AgentExecutionTrace).filter_by(workflow_node_execution_id=node.id).one()
    body = agent_execution_trace_to_dict(trace)
    assert body["status"] == "succeeded"
    assert body["attempt"] == 1
    assert body["input_summary"]["config_keys"] == ["instruction"]
    assert "api_token" not in body["input_summary"]["input_keys"]
    assert {"metric", "tool_calls", "cost_summary", "evaluation_summary", "version_metadata"}.issubset(
        set(body["output_summary"]["output_keys"])
    )
    assert "token_usage" not in body["output_summary"]["output_keys"]
    assert body["tool_calls"] == [{"name": "sql.query", "arg_keys": ["query"]}]
    assert body["token_usage"] == {"prompt_tokens": 120, "completion_tokens": 30}
    assert body["cost_summary"] == {"usd": 0.04}
    assert body["evaluation_summary"] == {"auc": 0.91}
    assert body["version_metadata"] == {"agent_version": "m22.1"}
    assert "do-not-store" not in json.dumps(body)

    response = client.get(f"/v1/runs/{run.id}/agent-traces?workspace_id={workspace.id}")
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["id"] == str(trace.id)


def test_worker_records_failed_agent_trace_without_secret_leak(seeded_db):
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    run = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key="trace-failure",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex}",
        parameters={},
        input_artifact_ids=[],
    )
    node = WorkflowNodeExecution(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        node_id="agent-step",
        node_type="failing.agent",
        execution_index=0,
        status="queued",
        inputs_json=json.dumps({"config": {"instruction": "fail"}}),
        logs_json="[]",
    )
    db.add(node)
    db.flush()

    def _executor(ctx: NodeExecutionContext) -> dict:
        raise RuntimeError("failed to connect mssql://user:password@db-host with api_token=secret")

    status = WorkflowWorker(node_executors={"failing.agent": _executor})._execute_node(db, run, node)
    db.commit()

    assert status == "failed"
    trace = db.query(AgentExecutionTrace).filter_by(workflow_node_execution_id=node.id).one()
    body = agent_execution_trace_to_dict(trace)
    assert body["status"] == "failed"
    assert "mssql://[redacted]@db-host" in body["error_summary"]
    assert "password" not in body["error_summary"]
    assert "api_token" not in body["error_summary"]


@pytest.mark.real_llm
def test_worker_runs_real_data_cleaning_agent_with_openai(seeded_db, tmp_path, monkeypatch):
    import pandas as pd

    api_key = os.environ.get("OPENCODE_API_KEY") or os.environ.get("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        pytest.skip("No LLM API key (OPENCODE_API_KEY or OPENAI_API_KEY) set for real LLM test")

    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    repo_root = Path(__file__).resolve().parents[3]
    source_path = upload_dir / "churn_sample.csv"
    sample_path = repo_root / "ai-data-science-team" / "data" / "churn_data.csv"
    if sample_path.exists():
        pd.read_csv(sample_path).head(12).to_csv(source_path, index=False)
    else:
        pd.DataFrame(
            {
                "customer_id": [f"c{i}" for i in range(12)],
                "tenure": [1, 3, 6, 9, 12, 18, 24, 30, 36, 42, 48, 60],
                "monthly_charges": [29.9, 44.2, 35.0, 71.3, 63.8, 82.1, 55.4, 92.0, 76.5, 61.0, 88.8, 49.7],
                "Churn": ["Yes", "No", "No", "Yes", "No", "No", "No", "Yes", "No", "No", "Yes", "No"],
            }
        ).to_csv(source_path, index=False)

    monkeypatch.setattr(settings, "openai_api_key", api_key)
    monkeypatch.setattr(settings, "artifact_storage_backend", "local")
    monkeypatch.setattr(settings, "artifact_storage_local_dir", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "chat_upload_dir", str(upload_dir))

    run = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key="clean-test",
        prefect_flow_run_id=f"prefect-{uuid.uuid4().hex}",
        parameters={"target_variable": "Churn"},
        input_artifact_ids=[],
    )
    source = Artifact(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="dataset",
        uri=str(source_path),
        created_by_user_id=user.id,
    )
    db.add(source)
    db.flush()
    run.input_artifact_ids_json = json.dumps([str(source.id)])
    node = WorkflowNodeExecution(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        node_id="clean",
        node_type="data.clean",
        execution_index=0,
        status="queued",
        inputs_json=json.dumps({"config": {"strategy": "auto"}}),
        logs_json="[]",
    )
    db.add(node)
    db.flush()

    status = WorkflowWorker()._execute_node(db, run, node)

    if status == "failed" and node.error and "insufficient_quota" in node.error:
        pytest.skip(f"OpenAI quota unavailable for real LLM workflow executor test: {node.error}")

    assert status == "succeeded", node.error
    outputs = json.loads(node.outputs_json)
    assert outputs["rows"] > 0
    artifact_ids = json.loads(node.produced_artifact_ids_json)
    assert artifact_ids
    artifact = db.get(Artifact, uuid.UUID(artifact_ids[0]))
    assert artifact.kind == "dataset"
    assert artifact.produced_by_node_id == "clean"
    assert Path(artifact.uri).exists()


def test_production_profile_refuses_local_artifact_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "deployment_profile", "production")
    monkeypatch.setattr(settings, "artifact_storage_backend", "local")
    monkeypatch.setattr(settings, "chat_upload_dir", str(tmp_path / "uploads"))

    with pytest.raises(RuntimeError, match="object storage"):
        settings.validate_directories()
