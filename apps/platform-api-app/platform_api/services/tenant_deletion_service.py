"""Tenant deletion service with database and external-system cleanup.

This service handles complete deletion of a tenant and its associated data,
including:
- Database records
- Local filesystem uploads and artifacts
- Cloud-backed artifact objects (best effort)
- Redis-backed cache and scheduled jobs
- Prefect scheduled deployments
- Outbox and DLQ records that are not covered by FK cascades

Security: Only tenant owners can delete a tenant. All deletions are logged.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_data_science_team.utils.agent_cache import get_agent_cache
from platform_api.core.config import settings
from platform_api.core.service_errors import ForbiddenError, NotFoundError
from platform_api.db.models import (
    Artifact,
    ChatSession,
    ChatUpload,
    DataSource,
    HitlApproval,
    Invite,
    OutboxDlq,
    Tenant,
    TenantMembership,
    TenantRole,
    WorkflowRun,
    WorkflowSignalEvent,
    WorkflowSpec,
    Workspace,
)
from platform_api.scheduler.job_queue import ScheduledJobQueue
from platform_api.services.outbox import OutboxEvent
from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

logger = logging.getLogger(__name__)


def require_tenant_owner(db: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Tenant:
    """Verify that the user is the owner of the tenant."""
    tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Tenant not found")

    membership = db.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    ).scalar_one_or_none()

    if membership is None or membership.role != TenantRole.owner:
        raise ForbiddenError("Only tenant owner can delete the tenant")

    return tenant


def _rowcount(result: Any) -> int:
    count = getattr(result, "rowcount", 0)
    return count if isinstance(count, int) and count >= 0 else 0


def _is_cloud_uri(uri: str | None) -> bool:
    return bool(uri and uri.startswith(("s3://", "gs://", "az://")))


def _is_remote_http_artifact(uri: str | None) -> bool:
    return bool(uri and uri.startswith(("http://", "https://")))


def _artifact_local_path(base_upload_dir: Path, uri: str) -> Path:
    return (base_upload_dir / uri).resolve()


def _safe_relative_to(path: Path, base_dir: Path) -> bool:
    try:
        path.relative_to(base_dir)
        return True
    except ValueError:
        return False


def _delete_s3_uri(uri: str) -> None:
    import boto3

    parsed = urlparse(uri)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI: {uri}")
    boto3.client("s3").delete_object(Bucket=bucket, Key=key)


def _delete_gcs_uri(uri: str) -> None:
    from google.cloud import storage

    parsed = urlparse(uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip("/")
    if not bucket_name or not blob_name:
        raise ValueError(f"Invalid GCS URI: {uri}")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    bucket.blob(blob_name).delete()


def _delete_azure_blob_uri(uri: str) -> None:
    from azure.storage.blob import BlobServiceClient

    if uri.startswith("az://"):
        parsed = urlparse(uri)
        container = parsed.netloc
        blob_name = parsed.path.lstrip("/")
        account_url = os.environ.get("AZURE_STORAGE_ACCOUNT_URL")
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if connection_string:
            client = BlobServiceClient.from_connection_string(connection_string)
        elif account_url:
            client = BlobServiceClient(account_url=account_url)
        else:
            raise RuntimeError(
                "Azure blob cleanup requires AZURE_STORAGE_CONNECTION_STRING "
                "or AZURE_STORAGE_ACCOUNT_URL for az:// URIs"
            )
    else:
        parsed = urlparse(uri)
        host_parts = parsed.netloc.split(".")
        if len(host_parts) < 1:
            raise ValueError(f"Invalid Azure blob URI: {uri}")
        account_name = host_parts[0]
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) != 2:
            raise ValueError(f"Invalid Azure blob URI: {uri}")
        container, blob_name = path_parts
        client = BlobServiceClient(
            account_url=f"{parsed.scheme}://{account_name}.blob.core.windows.net"
        )

    if not container or not blob_name:
        raise ValueError(f"Invalid Azure blob URI: {uri}")
    client.get_blob_client(container=container, blob=blob_name).delete_blob(delete_snapshots="include")


def _delete_cloud_artifact(uri: str) -> None:
    if uri.startswith("s3://"):
        _delete_s3_uri(uri)
        return
    if uri.startswith("gs://"):
        _delete_gcs_uri(uri)
        return
    if uri.startswith("az://") or "blob.core.windows.net" in uri:
        _delete_azure_blob_uri(uri)
        return
    raise ValueError(f"Unsupported cloud artifact URI: {uri}")


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover - defensive threading path
            error["exc"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if "exc" in error:
        raise error["exc"]
    return result.get("value")


def _cleanup_prefect_deployments(db: Session, tenant_id: uuid.UUID) -> tuple[int, list[str]]:
    try:
        service = WorkflowSchedulerService(db)
        result = _run_async(service.delete_scheduled_deployments(tenant_id=tenant_id))
    except Exception as exc:
        logger.warning("Failed to delete Prefect deployments for tenant %s: %s", tenant_id, exc)
        return 0, [str(exc)]

    if not isinstance(result, dict):
        return 0, ["Unexpected Prefect cleanup response"]
    return int(result.get("deleted", 0)), list(result.get("errors", []))


def _cleanup_redis_state(tenant_id: uuid.UUID) -> tuple[dict[str, int], list[str]]:
    stats = {"cache_entries_deleted": 0, "scheduled_jobs_deleted": 0, "scheduled_stream_entries_deleted": 0}
    errors: list[str] = []

    try:
        cache = get_agent_cache(redis_url=settings.agent_cache_redis_url or None)
        stats["cache_entries_deleted"] = cache.clear_tenant(str(tenant_id))
    except Exception as exc:
        logger.warning("Failed to clear agent cache for tenant %s: %s", tenant_id, exc)
        errors.append(f"agent_cache: {exc}")

    if settings.agent_cache_redis_url:
        try:
            queue = ScheduledJobQueue(settings.agent_cache_redis_url)
            queue_stats = queue.purge_tenant_data(str(tenant_id))
            stats["scheduled_jobs_deleted"] = int(queue_stats.get("jobs_deleted", 0))
            stats["scheduled_stream_entries_deleted"] = int(
                queue_stats.get("stream_entries_deleted", 0)
            )
        except Exception as exc:
            logger.warning("Failed to purge scheduled jobs for tenant %s: %s", tenant_id, exc)
            errors.append(f"scheduled_jobs: {exc}")

    return stats, errors


def delete_tenant(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    delete_audit_logs: bool = False,
) -> dict:
    """Delete a tenant and all associated database, filesystem, and external data."""
    tenant = require_tenant_owner(db, tenant_id=tenant_id, user_id=user_id)

    stats = {
        "tenant_id": str(tenant_id),
        "tenant_name": tenant.name,
        "files_deleted": 0,
        "cloud_objects_deleted": 0,
        "workspaces_deleted": 0,
        "users_removed": 0,
        "audit_logs_deleted": 0,
        "outbox_events_deleted": 0,
        "dlq_events_deleted": 0,
        "cache_entries_deleted": 0,
        "scheduled_jobs_deleted": 0,
        "scheduled_stream_entries_deleted": 0,
        "prefect_deployments_deleted": 0,
        "file_deletion_errors": [],
        "external_cleanup_errors": [],
    }

    base_upload_dir = Path(settings.chat_upload_dir).resolve()
    tenant_dir = (base_upload_dir / str(tenant_id)).resolve()

    files_to_delete: list[Path] = []
    if tenant_dir.exists() and _safe_relative_to(tenant_dir, base_upload_dir):
        files_to_delete = [path for path in tenant_dir.rglob("*") if path.is_file()]

    artifact_files_to_delete: list[Path] = []
    cloud_uris_to_delete: list[str] = []

    try:
        workspaces = db.execute(
            select(Workspace).where(Workspace.tenant_id == tenant_id)
        ).scalars().all()
        stats["workspaces_deleted"] = len(workspaces)

        memberships = db.execute(
            select(TenantMembership).where(TenantMembership.tenant_id == tenant_id)
        ).scalars().all()
        stats["users_removed"] = len(memberships)

        artifacts = db.execute(
            select(Artifact).where(Artifact.tenant_id == tenant_id)
        ).scalars().all()
        uploads = db.execute(
            select(ChatUpload).where(ChatUpload.tenant_id == tenant_id)
        ).scalars().all()

        for artifact in artifacts:
            uri = artifact.uri
            if not uri or _is_remote_http_artifact(uri):
                continue
            if _is_cloud_uri(uri):
                cloud_uris_to_delete.append(uri)
                continue
            file_path = _artifact_local_path(base_upload_dir, uri)
            if file_path.exists() and _safe_relative_to(file_path, base_upload_dir):
                artifact_files_to_delete.append(file_path)

        for upload in uploads:
            storage_uri = upload.storage_uri
            if _is_cloud_uri(storage_uri):
                cloud_uris_to_delete.append(storage_uri)

        db.execute(delete(WorkflowSignalEvent).where(WorkflowSignalEvent.tenant_id == tenant_id))
        db.execute(delete(ChatUpload).where(ChatUpload.tenant_id == tenant_id))
        db.execute(delete(ChatSession).where(ChatSession.tenant_id == tenant_id))
        db.execute(delete(HitlApproval).where(HitlApproval.tenant_id == tenant_id))
        db.execute(delete(Artifact).where(Artifact.tenant_id == tenant_id))
        db.execute(delete(WorkflowSpec).where(WorkflowSpec.tenant_id == tenant_id))
        db.execute(delete(DataSource).where(DataSource.tenant_id == tenant_id))
        db.execute(delete(WorkflowRun).where(WorkflowRun.tenant_id == tenant_id))
        db.execute(delete(Invite).where(Invite.tenant_id == tenant_id))
        db.execute(delete(Workspace).where(Workspace.tenant_id == tenant_id))
        db.execute(delete(TenantMembership).where(TenantMembership.tenant_id == tenant_id))

        outbox_result = db.execute(delete(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id))
        stats["outbox_events_deleted"] = _rowcount(outbox_result)
        dlq_result = db.execute(delete(OutboxDlq).where(OutboxDlq.tenant_id == tenant_id))
        stats["dlq_events_deleted"] = _rowcount(dlq_result)

        if delete_audit_logs:
            from platform_api.db.models import AuditLog

            result = db.execute(delete(AuditLog).where(AuditLog.tenant_id == tenant_id))
            stats["audit_logs_deleted"] = _rowcount(result)

        db.delete(tenant)
        db.commit()

        logger.info(
            "Tenant DB records deleted: %s (tenant_id=%s, workspaces=%d, users=%d). "
            "Deleting external tenant data...",
            tenant.name,
            tenant_id,
            stats["workspaces_deleted"],
            stats["users_removed"],
        )

        if tenant_dir.exists():
            try:
                shutil.rmtree(tenant_dir)
                stats["files_deleted"] += len(files_to_delete)
            except Exception as exc:
                error_msg = f"tenant_dir: {exc}"
                logger.error("Failed to delete tenant upload directory %s: %s", tenant_dir, exc)
                stats["file_deletion_errors"].append(error_msg)

        for file_path in artifact_files_to_delete:
            try:
                if file_path.exists():
                    file_path.unlink()
                    stats["files_deleted"] += 1
            except Exception as exc:
                error_msg = f"{file_path}: {exc}"
                logger.warning("Failed to delete artifact file %s: %s", file_path, exc)
                stats["file_deletion_errors"].append(error_msg)

        for uri in sorted(set(cloud_uris_to_delete)):
            try:
                _delete_cloud_artifact(uri)
                stats["cloud_objects_deleted"] += 1
            except Exception as exc:
                logger.warning("Failed to delete cloud artifact %s: %s", uri, exc)
                stats["external_cleanup_errors"].append(f"cloud_artifact:{uri}: {exc}")

        redis_stats, redis_errors = _cleanup_redis_state(tenant_id)
        stats.update(redis_stats)
        stats["external_cleanup_errors"].extend(redis_errors)

        deployments_deleted, prefect_errors = _cleanup_prefect_deployments(db, tenant_id)
        stats["prefect_deployments_deleted"] = deployments_deleted
        stats["external_cleanup_errors"].extend(f"prefect: {err}" for err in prefect_errors)

        logger.info(
            "Tenant deletion complete: %s (tenant_id=%s, files=%d, cloud=%d, cache=%d, jobs=%d, prefect=%d, errors=%d)",
            tenant.name,
            tenant_id,
            stats["files_deleted"],
            stats["cloud_objects_deleted"],
            stats["cache_entries_deleted"],
            stats["scheduled_jobs_deleted"],
            stats["prefect_deployments_deleted"],
            len(stats["file_deletion_errors"]) + len(stats["external_cleanup_errors"]),
        )
        return stats
    except Exception:
        db.rollback()
        logger.exception("Failed to delete tenant %s", tenant_id)
        raise
