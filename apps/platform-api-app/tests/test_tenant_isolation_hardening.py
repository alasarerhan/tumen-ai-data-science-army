from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from platform_api.db.models import TenantRole
from platform_api.tenant_context import clear_tenant_context, get_current_tenant_id


@pytest.mark.asyncio
async def test_require_tenant_admin_sets_tenant_context():
    from platform_api.authz.dependencies import require_tenant_admin

    tenant_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    membership = SimpleNamespace(role=TenantRole.admin)
    db = MagicMock()
    db.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    db.execute.side_effect = [
        SimpleNamespace(scalar_one_or_none=lambda: membership),
        None,
    ]

    with patch("platform_api.authz.dependencies.get_or_create_user", return_value=user):
        clear_tenant_context()
        result = await require_tenant_admin(
            tenant_id=str(tenant_id),
            principal=MagicMock(),
            db=db,
        )

    assert result["tenant_id"] == tenant_id
    assert get_current_tenant_id() == tenant_id
    assert db.execute.call_count == 2
    clear_tenant_context()


@pytest.mark.asyncio
async def test_admin_routes_scope_dlq_and_queue_stats_by_tenant():
    from platform_api.routes import admin

    tenant_id = uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    outbox = MagicMock()
    outbox.get_dlq_events.return_value = []
    outbox.get_queue_stats.return_value = {"pending": 1, "processing": 0, "failed": 0, "dlq": 0}

    with patch("platform_api.services.outbox.OutboxService", return_value=outbox):
        await admin.list_dlq_events(
            unreviewed_only=True,
            context={"tenant_id": tenant_id, "user": user},
            db=MagicMock(),
        )
        await admin.get_queue_stats(
            context={"tenant_id": tenant_id, "user": user},
            db=MagicMock(),
        )

    outbox.get_dlq_events.assert_called_once_with(
        limit=100,
        unreviewed_only=True,
        tenant_id=tenant_id,
    )
    outbox.get_queue_stats.assert_called_once_with(tenant_id=tenant_id)


@pytest.mark.asyncio
async def test_finops_routes_pass_tenant_scope():
    from platform_api.routes import finops

    tenant_id = uuid.uuid4()
    db = MagicMock()
    context = {"tenant_id": tenant_id}

    with patch.object(finops, "cleanup_expired_artifacts", return_value={"dry_run": True, "artifacts_deleted": 0, "files_deleted": 0, "bytes_freed": 0, "errors": []}) as cleanup_mock:
        await finops.run_artifact_cleanup(
            body=finops.CleanupRequest(dry_run=True),
            context=context,
            db=db,
        )

    cleanup_mock.assert_called_once_with(db, tenant_id=tenant_id, dry_run=True)

    fake_artifact = SimpleNamespace(id=uuid.uuid4(), kind="report", uri="tenant-a/file.csv", expires_at=None)
    with patch.object(finops, "list_expired_artifacts", return_value=[fake_artifact]) as expired_mock:
        response = await finops.list_expired(context=context, db=db)

    expired_mock.assert_called_once_with(db, tenant_id=tenant_id)
    assert response["count"] == 1


@pytest.mark.asyncio
async def test_scheduler_get_job_denies_cross_workspace_access():
    from platform_api.routes import scheduler

    workspace = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4())
    foreign_job = {
        "id": "job-1",
        "tenant_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "status": "queued",
    }
    fake_queue = MagicMock()
    fake_queue.get_job.return_value = foreign_job

    with patch.object(scheduler, "ScheduledJobQueue", return_value=fake_queue):
        with pytest.raises(HTTPException) as exc_info:
            await scheduler.get_job(
                job_id="job-1",
                context={"workspace": workspace},
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_scheduler_stats_only_count_workspace_jobs():
    from platform_api.routes import scheduler

    workspace = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4())
    local_job = {
        "id": "local",
        "tenant_id": str(workspace.tenant_id),
        "workspace_id": str(workspace.id),
        "status": "queued",
    }
    foreign_job = {
        "id": "foreign",
        "tenant_id": str(uuid.uuid4()),
        "workspace_id": str(uuid.uuid4()),
        "status": "queued",
    }
    fake_queue = MagicMock()
    fake_queue.get_jobs_by_status.side_effect = lambda status: ["local", "foreign"] if status == "queued" else []
    fake_queue.get_job.side_effect = lambda job_id: local_job if job_id == "local" else foreign_job

    with patch.object(scheduler, "ScheduledJobQueue", return_value=fake_queue):
        stats = await scheduler.get_queue_stats(context={"workspace": workspace})

    assert stats["queued"] == 1
    assert stats["dead_letter"] == 0


@pytest.mark.asyncio
async def test_workflow_schedule_routes_pass_workspace_scope():
    from platform_api.routes import workflows

    workspace = SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4())
    service = MagicMock()
    service.list_scheduled_deployments = AsyncMock(return_value=[{"id": "dep-1"}])
    service.pause_scheduled_deployment = AsyncMock(return_value={"deployment_id": "dep-1", "status": "paused"})
    service.resume_scheduled_deployment = AsyncMock(return_value={"deployment_id": "dep-1", "status": "resumed"})

    with patch("platform_api.services.workflow_scheduler_service.WorkflowSchedulerService", return_value=service):
        await workflows.list_schedules(
            context={"workspace": workspace},
            db=MagicMock(),
        )
        await workflows.pause_schedule(
            deployment_id="dep-1",
            context={"workspace": workspace},
            db=MagicMock(),
        )
        await workflows.resume_schedule(
            deployment_id="dep-1",
            context={"workspace": workspace},
            db=MagicMock(),
        )

    service.list_scheduled_deployments.assert_called_once_with(
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )
    service.pause_scheduled_deployment.assert_called_once_with(
        "dep-1",
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )
    service.resume_scheduled_deployment.assert_called_once_with(
        "dep-1",
        workspace_id=workspace.id,
        tenant_id=workspace.tenant_id,
    )
