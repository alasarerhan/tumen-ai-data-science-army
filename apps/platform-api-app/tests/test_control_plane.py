from __future__ import annotations

import inspect
import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.control_plane.catalog import catalog_resource_keys, get_non_queryable_surfaces
from platform_api.control_plane.query import build_context_for_chat_session, chat_platform_reply
from platform_api.db.models import (
    AgentExecutionTrace,
    AuditLog,
    Artifact,
    DataSource,
    TenantMembership,
    TenantRole,
    WorkflowNodeExecution,
    WorkflowRun,
    WorkflowSpec,
)
from platform_api.db.session import get_db
from platform_api.main import create_app
from platform_api.services.chat_service import create_chat_session, generate_assistant_reply


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


def _seed_workflow_and_run(seeded_db):
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    workflow = WorkflowSpec(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        name="Revenue Pipeline",
        version=1,
        status="published",
        spec_json=json.dumps({"name": "Revenue Pipeline", "steps": [{"id": "s1", "tool": "data_clean"}]}),
        created_by_user_id=user.id,
    )
    db.add(workflow)
    db.flush()
    run = WorkflowRun(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        requested_by_user_id=user.id,
        flow_key="Revenue Pipeline",
        workflow_spec_id=workflow.id,
        workflow_version=workflow.version,
        trigger_type="manual",
        input_artifact_ids_json="[]",
        prefect_flow_run_id=f"prefect-{uuid.uuid4()}",
        status="RUNNING",
        parameters_json=json.dumps({"target": "revenue"}),
    )
    db.add(run)
    db.flush()
    return workflow, run


def test_catalog_covers_core_platform_surfaces() -> None:
    keys = catalog_resource_keys()

    assert "workflows" in keys
    assert "runs" in keys
    assert "data_sources" in keys
    assert "release.docs" in keys
    assert "agents.catalog" in keys
    assert any(item.surface_key == "secrets.raw_values" for item in get_non_queryable_surfaces())


def test_control_plane_package_does_not_depend_on_dsml_agent_registry() -> None:
    import platform_api.control_plane.actions as actions
    import platform_api.control_plane.catalog as catalog
    import platform_api.control_plane.query as query

    combined = "\n".join(
        inspect.getsource(module)
        for module in [actions, catalog, query]
    )

    assert "ai_data_science_team" not in combined
    assert "ToolRegistry" not in combined
    assert "ChatWorkspace" not in combined


def test_query_returns_workflow_run_and_redacted_data_source(seeded_db):
    app, client = _client(seeded_db)
    _seed_workflow_and_run(seeded_db)
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    db.add(
        DataSource(
            tenant_id=workspace.tenant_id,
            workspace_id=workspace.id,
            name="SQL Server",
            kind="sql_server",
            connection_uri="mssql+pymssql://user:secret@sql.example:1433/warehouse",
            metadata_json=json.dumps({"host": "sql.example", "secret_ref": "ds-secret"}),
        )
    )
    db.flush()

    response = client.post(
        "/v1/control-plane/query",
        json={
            "workspace_id": str(workspace.id),
            "query": "platform status",
            "resource_keys": ["workflows", "runs", "data_sources"],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "platform_query_result"
    assert {section["resource_key"] for section in body["sections"]} == {"workflows", "runs", "data_sources"}
    ds_section = next(section for section in body["sections"] if section["resource_key"] == "data_sources")
    serialized_records = json.dumps(ds_section["records"])
    assert "secret_ref" not in serialized_records
    assert "ds-secret" not in serialized_records
    assert "mssql+pymssql://user:secret@" not in serialized_records
    assert ds_section["provenance"]["redactions"]


def test_query_marks_admin_resources_access_denied_for_workspace_member(seeded_db):
    app = create_app()
    user = seeded_db["user_member"]
    principal = Principal(sub=user.sub, email=user.email, claims={})

    def _principal():
        return principal

    def _db():
        yield seeded_db["db"]

    app.dependency_overrides[get_principal] = _principal
    app.dependency_overrides[get_db] = _db
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/control-plane/query",
            json={
                "workspace_id": str(seeded_db["workspace"].id),
                "query": "audit status",
                "resource_keys": ["governance.audit"],
            },
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    section = response.json()["sections"][0]
    assert section["status"] == "access_denied"


def test_query_returns_expanded_scheduler_modelops_lineage_and_docs(seeded_db):
    app, client = _client(seeded_db)
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    _workflow, run = _seed_workflow_and_run(seeded_db)
    scheduled = WorkflowSpec(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        name="Scheduled Model Pipeline",
        version=1,
        status="published",
        spec_json=json.dumps(
            {
                "schedule": {"cron": "0 8 * * 1-5", "timezone": "UTC", "enabled": True},
                "steps": [{"id": "train", "tool": "model_train"}],
            }
        ),
        created_by_user_id=user.id,
    )
    parent = Artifact(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="dataset",
        uri="local://artifacts/dataset.csv",
        produced_by_node_id="profile",
        created_by_user_id=user.id,
    )
    db.add_all([scheduled, parent])
    db.flush()
    model = Artifact(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="model",
        uri="s3://private-bucket/model.bin?sig=secret",
        produced_by_node_id="train",
        parent_artifact_ids_json=json.dumps([str(parent.id)]),
        created_by_user_id=user.id,
    )
    metrics = Artifact(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        kind="metrics",
        uri="local://artifacts/metrics.json",
        produced_by_node_id="evaluate",
        parent_artifact_ids_json=json.dumps([str(model.id)]),
        created_by_user_id=user.id,
    )
    db.add_all([model, metrics])
    db.flush()

    response = client.post(
        "/v1/control-plane/query",
        json={
            "workspace_id": str(workspace.id),
            "query": "scheduler model lineage docs",
            "resource_keys": ["workflow.schedules", "artifacts", "modelops", "release.docs"],
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    sections = {section["resource_key"]: section for section in response.json()["sections"]}
    assert sections["workflow.schedules"]["status"] == "ok"
    assert sections["workflow.schedules"]["records"][0]["cron"] == "0 8 * * 1-5"
    assert sections["artifacts"]["relationships"]
    assert any(rel["relationship_type"] == "parent_of" for rel in sections["artifacts"]["relationships"])
    assert sections["modelops"]["status"] == "ok"
    assert sections["modelops"]["metrics"]["registered_models"] == 1
    assert sections["modelops"]["metrics"]["monitor_snapshots"] == 1
    assert sections["modelops"]["records"][0]["monitoring_status"] == "linked"
    docs = sections["release.docs"]
    assert docs["metrics"]["existing_documents"] >= 1
    assert any(record["path"] == "docs/universal-platform-control-plane.md" for record in docs["records"])


def test_finops_query_requires_tenant_admin_and_returns_safe_summary(seeded_db):
    app, client = _client(seeded_db)
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    db.add(
        Artifact(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            kind="report",
            uri="local://artifacts/old-report.html",
            expires_at=datetime.now(UTC) - timedelta(days=1),
            created_by_user_id=user.id,
        )
    )
    _workflow, run = _seed_workflow_and_run(seeded_db)
    node = WorkflowNodeExecution(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        node_id="llm-plan",
        node_type="control_plane.summarize",
        execution_index=0,
        status="succeeded",
        inputs_json="{}",
        logs_json="[]",
    )
    db.add(node)
    db.flush()
    db.add(
        AgentExecutionTrace(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            workflow_run_id=run.id,
            workflow_node_execution_id=node.id,
            node_id=node.node_id,
            node_type=node.node_type,
            executor_kind="llm",
            status="succeeded",
            started_at=datetime.now(UTC),
            cost_summary_json=json.dumps({"usd": 0.123456}),
            token_usage_json=json.dumps({"prompt_tokens": 120, "completion_tokens": 80}),
        )
    )
    db.flush()

    denied = client.post(
        "/v1/control-plane/query",
        json={"workspace_id": str(workspace.id), "query": "cost", "resource_keys": ["finops.cost"]},
    )
    assert denied.status_code == 200
    assert denied.json()["sections"][0]["status"] == "access_denied"

    db.add(TenantMembership(tenant_id=tenant.id, user_id=user.id, role=TenantRole.admin))
    db.flush()
    allowed = client.post(
        "/v1/control-plane/query",
        json={"workspace_id": str(workspace.id), "query": "cost", "resource_keys": ["finops.cost"]},
    )

    app.dependency_overrides.clear()
    assert allowed.status_code == 200
    section = allowed.json()["sections"][0]
    assert section["status"] == "ok"
    assert section["records"][0]["expired_artifacts"] == 1
    assert section["records"][0]["agent_trace_cost_usd"] == 0.123456
    assert section["records"][0]["total_tokens"] == 200
    assert section["records"][0]["billing_grade"] == "trace_reported_estimate"
    assert "recommendations" in section["records"][0]


def test_action_execute_requires_confirmation_and_writes_audit_log(seeded_db):
    app, client = _client(seeded_db)
    _workflow, run = _seed_workflow_and_run(seeded_db)
    workspace = seeded_db["workspace"]

    planned = client.post(
        "/v1/control-plane/actions/execute",
        json={
            "workspace_id": str(workspace.id),
            "action_name": "runs.cancel",
            "arguments": {"run_id": str(run.id)},
            "confirmed": False,
        },
    )
    assert planned.status_code == 200
    assert planned.json()["status"] == "planned"

    executed = client.post(
        "/v1/control-plane/actions/execute",
        json={
            "workspace_id": str(workspace.id),
            "action_name": "runs.cancel",
            "arguments": {"run_id": str(run.id)},
            "confirmed": True,
        },
    )

    app.dependency_overrides.clear()
    assert executed.status_code == 200
    assert executed.json()["status"] == "executed"
    assert executed.json()["audit_id"]
    db = seeded_db["db"]
    db.refresh(run)
    assert run.status == "CANCELLED"
    audit = db.get(AuditLog, uuid.UUID(executed.json()["audit_id"]))
    assert audit is not None
    assert audit.action == "control_plane.runs.cancel"


def test_action_plan_accepts_natural_language_query(seeded_db):
    app, client = _client(seeded_db)
    _workflow, run = _seed_workflow_and_run(seeded_db)
    workspace = seeded_db["workspace"]

    response = client.post(
        "/v1/control-plane/actions/plan",
        json={
            "workspace_id": str(workspace.id),
            "query": f"cancel run {run.id}",
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert body["action_name"] == "runs.cancel"
    assert body["allowed"] is True
    assert body["confirmation_required"] is True
    assert body["arguments"]["run_id"] == str(run.id)


def test_chat_platform_query_returns_platform_query_artifact(seeded_db):
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    _seed_workflow_and_run(seeded_db)
    session = create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        title="control",
    )

    text, artifacts = generate_assistant_reply(db, session=session, prompt="platform status")

    assert "Control plane resolved" in text
    assert artifacts[0]["type"] == "platform_query_result"
    assert "workflows" in artifacts[0]["plan"]["resource_keys"]


def test_control_plane_queries_agent_execution_traces(seeded_db):
    app, client = _client(seeded_db)
    db = seeded_db["db"]
    workspace = seeded_db["workspace"]
    _workflow, run = _seed_workflow_and_run(seeded_db)
    node = WorkflowNodeExecution(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        node_id="train",
        node_type="model.train",
        execution_index=0,
        status="succeeded",
        inputs_json=json.dumps({}),
        logs_json="[]",
    )
    db.add(node)
    db.flush()
    trace = AgentExecutionTrace(
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run.id,
        workflow_node_execution_id=node.id,
        node_id=node.node_id,
        node_type=node.node_type,
        attempt=1,
        executor_kind=node.node_type,
        status="succeeded",
        input_summary_json=json.dumps({"input_keys": [], "config_keys": []}),
        output_summary_json=json.dumps({"output_keys": ["model"], "artifact_count": 1}),
        tool_calls_json=json.dumps([{"name": "h2o.train", "arg_keys": ["target"]}]),
        artifact_ids_json=json.dumps([]),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        duration_ms=12,
    )
    db.add(trace)
    db.commit()

    response = client.post(
        "/v1/control-plane/query",
        json={
            "workspace_id": str(workspace.id),
            "query": "agent traces",
            "resource_keys": ["agent.traces"],
            "filters": {"workflow_run_id": str(run.id)},
            "limit": 10,
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200, response.text
    section = response.json()["sections"][0]
    assert section["resource_key"] == "agent.traces"
    assert section["records"][0]["node_type"] == "model.train"
    assert section["records"][0]["tool_call_count"] == 1
    assert "private_reasoning" in section["provenance"]["redactions"]


def test_chat_platform_query_context_builder_uses_session_membership(seeded_db):
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    session = create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        title="control",
    )

    ctx = build_context_for_chat_session(db, session)
    assert ctx is not None
    reply = chat_platform_reply(ctx, "platform status")
    assert reply is not None


def test_chat_platform_query_does_not_call_chatworkspace(seeded_db):
    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    user = seeded_db["user_admin"]
    session = create_chat_session(
        db,
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        title="control",
    )

    with patch("platform_api.services.chat_service._try_chatworkspace_reply") as chatworkspace:
        generate_assistant_reply(db, session=session, prompt="platform status")

    chatworkspace.assert_not_called()
