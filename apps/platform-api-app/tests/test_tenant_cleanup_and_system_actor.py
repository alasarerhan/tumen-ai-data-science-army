from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from platform_api.db.models import (
    Artifact,
    ChatSession,
    ChatSessionStatus,
    ChatUpload,
    OutboxDlq,
    TenantMembership,
    TenantRole,
)
from platform_api.services.outbox import OutboxEvent, OutboxEventStatus
from platform_api.tenant_context import (
    clear_tenant_context,
    get_current_system_actor,
    get_current_tenant_id,
    set_tenant_context,
    system_actor_context,
)


def test_system_actor_context_restores_request_tenant_context() -> None:
    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    clear_tenant_context()
    set_tenant_context(tenant_id, workspace_id)

    assert get_current_tenant_id() == tenant_id
    assert get_current_system_actor() is False

    with system_actor_context():
        assert get_current_tenant_id() == tenant_id
        assert get_current_system_actor() is True

    assert get_current_tenant_id() == tenant_id
    assert get_current_system_actor() is False
    clear_tenant_context()


@pytest.mark.asyncio
async def test_scheduler_runs_handlers_as_explicit_system_actor(seeded_db: dict) -> None:
    from platform_api.services.scheduler_service import SchedulerService

    db = seeded_db["db"]
    service = SchedulerService(db)
    observed: dict[str, bool] = {}

    async def handler(job_db):
        observed["system_actor"] = get_current_system_actor()

    job = service.register_job(
        job_name="tenant-cleanup-check",
        job_type="maintenance",
        handler=handler,
        interval_seconds=60,
    )
    isolated_session_factory = sessionmaker(bind=db.bind, autocommit=False, autoflush=False)

    with patch("platform_api.db.session.SessionLocal", isolated_session_factory):
        await service._run_job(job)

    assert observed["system_actor"] is True


def test_delete_tenant_cleans_external_backends(seeded_db: dict, tmp_path, monkeypatch) -> None:
    from platform_api.services.tenant_deletion_service import delete_tenant

    db = seeded_db["db"]
    tenant = seeded_db["tenant"]
    workspace = seeded_db["workspace"]
    owner = seeded_db["user_admin"]

    db.add(
        TenantMembership(
            tenant_id=tenant.id,
            user_id=owner.id,
            role=TenantRole.owner,
        )
    )

    upload_root = tmp_path / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("platform_api.core.config.settings.chat_upload_dir", str(upload_root))

    tenant_file = upload_root / str(tenant.id) / "chat" / "upload.txt"
    tenant_file.parent.mkdir(parents=True, exist_ok=True)
    tenant_file.write_text("tenant-data", encoding="utf-8")

    artifact_file = upload_root / "artifacts" / "result.txt"
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text("artifact", encoding="utf-8")

    chat_session = ChatSession(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=owner.id,
        title="cleanup",
        status=ChatSessionStatus.active,
    )
    db.add(chat_session)
    db.flush()

    db.add_all(
        [
            Artifact(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                kind="local",
                uri=str(Path("artifacts") / "result.txt"),
            ),
            Artifact(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                kind="cloud",
                uri="s3://tenant-bucket/reports/run.json",
            ),
            ChatUpload(
                id=uuid.uuid4(),
                session_id=chat_session.id,
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                filename="cloud.csv",
                storage_uri="gs://tenant-bucket/uploads/cloud.csv",
                size_bytes=12,
            ),
            OutboxEvent(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                aggregate_type="workflow_run",
                aggregate_id="run-1",
                event_type="workflow_run.created",
                status=OutboxEventStatus.pending,
            ),
            OutboxDlq(
                tenant_id=tenant.id,
                workspace_id=workspace.id,
                original_event_id=uuid.uuid4(),
                aggregate_type="workflow_run",
                aggregate_id="run-1",
                event_type="workflow_run.failed",
                retry_count=5,
                original_created_at=datetime.now(UTC),
            ),
        ]
    )
    db.commit()

    deleted_cloud_uris: list[str] = []
    monkeypatch.setattr(
        "platform_api.services.tenant_deletion_service._delete_cloud_artifact",
        lambda uri: deleted_cloud_uris.append(uri),
    )
    monkeypatch.setattr(
        "platform_api.services.tenant_deletion_service._cleanup_redis_state",
        lambda tenant_id: (
            {
                "cache_entries_deleted": 4,
                "scheduled_jobs_deleted": 2,
                "scheduled_stream_entries_deleted": 3,
            },
            [],
        ),
    )
    monkeypatch.setattr(
        "platform_api.services.tenant_deletion_service._cleanup_prefect_deployments",
        lambda db, tenant_id: (5, []),
    )

    stats = delete_tenant(
        db,
        tenant_id=tenant.id,
        user_id=owner.id,
    )

    assert stats["outbox_events_deleted"] == 1
    assert stats["dlq_events_deleted"] == 1
    assert stats["cache_entries_deleted"] == 4
    assert stats["scheduled_jobs_deleted"] == 2
    assert stats["scheduled_stream_entries_deleted"] == 3
    assert stats["prefect_deployments_deleted"] == 5
    assert stats["cloud_objects_deleted"] == 2
    assert sorted(deleted_cloud_uris) == [
        "gs://tenant-bucket/uploads/cloud.csv",
        "s3://tenant-bucket/reports/run.json",
    ]
    assert tenant_file.exists() is False
    assert artifact_file.exists() is False
    assert db.get(type(tenant), tenant.id) is None


@pytest.mark.asyncio
async def test_workflow_scheduler_service_deletes_scoped_deployments(seeded_db: dict) -> None:
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    db = seeded_db["db"]
    service = WorkflowSchedulerService(db)
    service._prefect_available = True

    deployment_id = str(uuid.uuid4())
    service.list_scheduled_deployments = AsyncMock(return_value=[{"id": deployment_id}])

    delete_mock = AsyncMock()

    class FakeClientContext:
        async def __aenter__(self):
            class FakeClient:
                delete_deployment = delete_mock

            return FakeClient()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    prefect_module = ModuleType("prefect")
    prefect_client_module = ModuleType("prefect.client")
    prefect_orchestration_module = ModuleType("prefect.client.orchestration")
    prefect_orchestration_module.get_client = lambda: FakeClientContext()

    with patch.dict(
        "sys.modules",
        {
            "prefect": prefect_module,
            "prefect.client": prefect_client_module,
            "prefect.client.orchestration": prefect_orchestration_module,
        },
    ):
        result = await service.delete_scheduled_deployments(
            tenant_id=seeded_db["tenant"].id,
            workspace_id=seeded_db["workspace"].id,
        )

    assert result == {"deleted": 1, "errors": []}
    service.list_scheduled_deployments.assert_awaited_once_with(
        workspace_id=seeded_db["workspace"].id,
        tenant_id=seeded_db["tenant"].id,
    )
    delete_mock.assert_awaited_once()
