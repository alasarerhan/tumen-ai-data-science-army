from __future__ import annotations

import json

from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.models import Artifact, WorkflowRun
from platform_api.db.session import get_db
from platform_api.main import create_app


def _client(seeded_db):
    app = create_app()
    user = seeded_db["user_admin"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal():
        return principal

    def _db():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    return app, TestClient(app, raise_server_exceptions=False)


def test_modelops_summary_returns_artifact_backed_registry_and_retrain_candidate(seeded_db):
    app, client = _client(seeded_db)
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    run = WorkflowRun(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        requested_by_user_id=user.id,
        flow_key="model-pipeline",
        input_artifact_ids_json="[]",
        prefect_flow_run_id="prefect-modelops",
        status="COMPLETED",
        parameters_json="{}",
    )
    db.add(run)
    db.flush()
    model = Artifact(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="model",
        uri="s3://private-bucket/model.bin?token=redacted-by-scheme",
        produced_by_node_id="train",
        created_by_user_id=user.id,
    )
    db.add(model)
    db.flush()
    db.add(
        Artifact(
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            workflow_run_id=run.id,
            kind="drift_report",
            uri="local://artifacts/drift-warning.json",
            produced_by_node_id="evaluate",
            parent_artifact_ids_json=json.dumps([str(model.id)]),
            created_by_user_id=user.id,
        )
    )
    db.flush()

    response = client.get(f"/v1/modelops/summary?workspace_id={workspace.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["metrics"]["registered_models"] == 1
    assert body["metrics"]["monitor_snapshots"] == 1
    assert body["metrics"]["retrain_candidates"] == 1
    assert body["registry"][0]["uri_scheme"] == "s3"
    assert body["registry"][0]["monitoring_status"] == "linked"
    assert body["registry"][0]["drift_status"] == "warning"
    assert "private-bucket" not in json.dumps(body)


def test_modelops_admin_can_register_monitor_and_deployment_records(seeded_db):
    app, client = _client(seeded_db)
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    run = WorkflowRun(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        requested_by_user_id=user.id,
        flow_key="model-pipeline",
        input_artifact_ids_json="[]",
        prefect_flow_run_id="prefect-modelops-prod",
        status="COMPLETED",
        parameters_json="{}",
    )
    db.add(run)
    db.flush()
    model_artifact = Artifact(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="model",
        uri="s3://private-bucket/model.bin?secret=never-return",
        produced_by_node_id="train",
        created_by_user_id=user.id,
    )
    db.add(model_artifact)
    db.flush()

    registered = client.post(
        f"/v1/modelops/registry?workspace_id={workspace.id}",
        json={
            "model_name": "churn-risk",
            "version": "2026.06.09",
            "stage": "staging",
            "artifact_id": str(model_artifact.id),
            "workflow_run_id": str(run.id),
            "model_card": {"owner": "ml-platform"},
        },
    )
    assert registered.status_code == 201
    model_id = registered.json()["model_id"]

    monitored = client.post(
        f"/v1/modelops/monitors?workspace_id={workspace.id}",
        json={
            "model_id": model_id,
            "monitor_type": "drift",
            "status": "warning",
            "metric_name": "psi",
            "metric_value": 0.27,
            "threshold_value": 0.2,
            "remediation_workflow": "retrain_from_latest_data",
        },
    )
    assert monitored.status_code == 201

    deployed = client.post(
        f"/v1/modelops/deployments?workspace_id={workspace.id}",
        json={
            "model_id": model_id,
            "environment": "production",
            "status": "deployed",
            "endpoint_url": "https://models.example/churn?token=secret",
            "health_status": "healthy",
            "rollback_notes": "rollback to previous approved version",
        },
    )
    assert deployed.status_code == 201

    response = client.get(f"/v1/modelops/summary?workspace_id={workspace.id}")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["registry"] == "persisted"
    assert body["status"]["monitoring"] == "persisted"
    assert body["status"]["deployment"] == "persisted"
    assert body["metrics"]["registered_models"] == 1
    assert body["metrics"]["monitor_snapshots"] == 1
    assert body["metrics"]["deployments"] == 1
    assert body["metrics"]["retrain_candidates"] == 1
    assert body["registry"][0]["model_name"] == "churn-risk"
    assert body["deployments"][0]["endpoint_configured"] is True
    assert "token=secret" not in json.dumps(body)
