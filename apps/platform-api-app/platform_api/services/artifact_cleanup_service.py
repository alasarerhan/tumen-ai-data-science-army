"""Artifact cleanup service for storage cost optimization.

FinOps: Implements TTL-based artifact cleanup to prevent unbounded storage growth.
Runs as a background task or can be triggered via API.

NOTIFICATION HOOKS
------------------
Before artifacts are deleted, notification hooks are called. Implement
a notification handler by registering it:

    from platform_api.services.artifact_cleanup_service import register_deletion_handler

    def my_handler(artifacts: list[Artifact]) -> None:
        for artifact in artifacts:
            send_email(artifact.owner_email, f"Your artifact {artifact.name} will be deleted")

    register_deletion_handler(my_handler)

Usage
-----
::

    from platform_api.services.artifact_cleanup_service import cleanup_expired_artifacts

    # Clean up expired artifacts
    stats = cleanup_expired_artifacts(db, dry_run=False)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.db.models import Artifact

logger = logging.getLogger(__name__)

MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
MIN_BATCH_SIZE = 1
MAX_BATCH_SIZE = 1000

_deletion_handlers: List[Callable[[List[Artifact]], None]] = []


def register_deletion_handler(handler: Callable[[List[Artifact]], None]) -> None:
    """Register a handler to be called before artifact deletion.

    Handlers are called with the list of artifacts about to be deleted.
    Use this to send notifications, log audit trails, or trigger webhooks.

    Parameters
    ----------
    handler : Callable[[List[Artifact]], None]
        Function to call before deletion.
    """
    _deletion_handlers.append(handler)
    logger.info("Registered artifact deletion handler: %s", handler.__name__)


def _notify_deletion(artifacts: List[Artifact]) -> None:
    """Call all registered deletion handlers.

    Errors in handlers are logged but do not prevent deletion.
    """
    if not artifacts:
        return

    for handler in _deletion_handlers:
        try:
            handler(artifacts)
        except Exception as e:
            logger.error(
                "Deletion handler %s failed: %s. Deletion will continue.",
                handler.__name__,
                e
            )


def get_artifact_expiry_date() -> datetime:
    """Calculate expiry date based on retention policy.
    
    Raises
    ------
    ValueError
        If artifact_retention_days is not between MIN_RETENTION_DAYS and MAX_RETENTION_DAYS.
    """
    retention_days = settings.artifact_retention_days
    if retention_days < MIN_RETENTION_DAYS:
        raise ValueError(
            f"artifact_retention_days must be at least {MIN_RETENTION_DAYS} day(s), "
            f"got {retention_days}. Setting to 0 would delete all artifacts immediately."
        )
    if retention_days > MAX_RETENTION_DAYS:
        raise ValueError(
            f"artifact_retention_days must be at most {MAX_RETENTION_DAYS} days (10 years), "
            f"got {retention_days}."
        )
    return datetime.now(UTC) + timedelta(days=retention_days)


def mark_artifacts_for_expiry(
    db: Session,
    *,
    artifact_ids: list[uuid.UUID],
    expires_at: datetime | None = None,
) -> int:
    """Mark artifacts for future deletion.

    Parameters
    ----------
    db : Session
        Database session.
    artifact_ids : list[UUID]
        List of artifact IDs to mark.
    expires_at : datetime | None
        Expiry timestamp. Defaults to retention policy.

    Returns
    -------
    int
        Number of artifacts marked.
    """
    if not artifact_ids:
        return 0

    expiry = expires_at or get_artifact_expiry_date()

    result = db.execute(
        Artifact.__table__.update()
        .where(Artifact.id.in_(artifact_ids))
        .values(expires_at=expiry)
    )
    db.flush()
    logger.info("Marked %d artifacts for expiry at %s", result.rowcount, expiry)
    return result.rowcount


def list_expired_artifacts(
    db: Session,
    *,
    limit: int | None = None,
    tenant_id: uuid.UUID | str | None = None,
) -> list[Artifact]:
    """List all artifacts past their expiry date.

    Parameters
    ----------
    db : Session
        Database session.

    Returns
    -------
    list[Artifact]
        List of expired artifacts.
    """
    now = datetime.now(UTC)
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)

    query = select(Artifact).where(
        Artifact.expires_at.isnot(None),
        Artifact.expires_at < now,
    )
    if tenant_id is not None:
        query = query.where(Artifact.tenant_id == tenant_id)

    return list(
        db.execute(
            query.order_by(Artifact.expires_at.asc(), Artifact.id.asc()).limit(limit)
        ).scalars()
    )


def cleanup_expired_artifacts(
    db: Session,
    *,
    tenant_id: uuid.UUID | str | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """Delete expired artifacts and their files.

    Parameters
    ----------
    db : Session
        Database session.
    dry_run : bool
        If True, only report what would be deleted.
    batch_size : int
        Number of artifacts to process per batch. Must be between 1 and 1000.

    Returns
    -------
    dict
        Statistics about the cleanup operation.
    
    Raises
    ------
    ValueError
        If batch_size is outside valid range.
    """
    if batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
        raise ValueError(
            f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}, "
            f"got {batch_size}"
        )
    stats = {
        "dry_run": dry_run,
        "artifacts_deleted": 0,
        "files_deleted": 0,
        "bytes_freed": 0,
        "errors": [],
        "failed_file_deletions": [],
    }

    expired = list_expired_artifacts(db, limit=batch_size, tenant_id=tenant_id)
    if not expired:
        logger.info("No expired artifacts to clean up")
        return stats

    base_upload_dir = Path(settings.chat_upload_dir).resolve()

    files_to_delete: list[tuple[Path, Artifact]] = []
    for artifact in expired:
        uri = artifact.uri
        if uri and not uri.startswith(("http://", "https://", "s3://", "gs://", "az://")):
            file_path = base_upload_dir / uri
            if file_path.exists():
                files_to_delete.append((file_path, artifact))

    if dry_run:
        for file_path, artifact in files_to_delete:
            try:
                size = file_path.stat().st_size
                stats["files_deleted"] += 1
                stats["bytes_freed"] += size
            except Exception as e:
                stats["errors"].append(f"{file_path}: {e}")
        stats["artifacts_deleted"] = len(expired)
        return stats

    artifacts_to_delete = expired
    artifact_ids_to_delete = [a.id for a in artifacts_to_delete]

    _notify_deletion(artifacts_to_delete)

    try:
        db.execute(
            Artifact.__table__.delete().where(Artifact.id.in_(artifact_ids_to_delete))
        )
        db.commit()
        logger.info(
            "Deleted %d artifact records from database",
            len(artifact_ids_to_delete),
        )
    except Exception as e:
        db.rollback()
        stats["errors"].append(f"Database commit failed: {e}")
        logger.error("Failed to delete artifact records: %s", e)
        return stats

    stats["artifacts_deleted"] = len(artifact_ids_to_delete)

    for file_path, artifact in files_to_delete:
        try:
            size = file_path.stat().st_size
            file_path.unlink()
            stats["files_deleted"] += 1
            stats["bytes_freed"] += size
        except Exception as e:
            error_msg = f"{artifact.uri}: {e}"
            stats["errors"].append(error_msg)
            stats["failed_file_deletions"].append({
                "artifact_id": str(artifact.id),
                "uri": artifact.uri,
                "error": str(e),
            })
            logger.warning("Failed to delete artifact file %s: %s", file_path, e)

    logger.info(
        "Cleaned up %d expired artifacts (%d files, %d bytes, %d errors)",
        stats["artifacts_deleted"],
        stats["files_deleted"],
        stats["bytes_freed"],
        len(stats["errors"]),
    )

    return stats


def cleanup_old_artifacts(
    db: Session,
    *,
    tenant_id: uuid.UUID | str | None = None,
    older_than_days: int | None = None,
    dry_run: bool = False,
    batch_size: int = 100,
) -> dict:
    """Delete artifacts older than specified days (regardless of expires_at).

    Parameters
    ----------
    db : Session
        Database session.
    older_than_days : int | None
        Age threshold in days. Defaults to artifact_retention_days * 2.
        Must be at least MIN_RETENTION_DAYS.
    dry_run : bool
        If True, only report what would be deleted.
    batch_size : int
        Number of artifacts to process per batch. Must be between 1 and 1000.

    Returns
    -------
    dict
        Statistics about the cleanup operation.
    
    Raises
    ------
    ValueError
        If older_than_days or batch_size is outside valid range.
    """
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)

    if batch_size < MIN_BATCH_SIZE or batch_size > MAX_BATCH_SIZE:
        raise ValueError(
            f"batch_size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}, "
            f"got {batch_size}"
        )
    
    days = older_than_days or (settings.artifact_retention_days * 2)
    if days < MIN_RETENTION_DAYS:
        raise ValueError(
            f"older_than_days must be at least {MIN_RETENTION_DAYS} day(s), "
            f"got {days}. Setting to 0 would delete all artifacts."
        )
    if days > MAX_RETENTION_DAYS:
        raise ValueError(
            f"older_than_days must be at most {MAX_RETENTION_DAYS} days, "
            f"got {days}."
        )
    
    threshold = datetime.now(UTC) - timedelta(days=days)

    stats = {
        "dry_run": dry_run,
        "threshold_days": days,
        "artifacts_deleted": 0,
        "files_deleted": 0,
        "bytes_freed": 0,
        "errors": [],
        "failed_file_deletions": [],
    }

    query = select(Artifact).where(Artifact.created_at < threshold)
    if tenant_id is not None:
        query = query.where(Artifact.tenant_id == tenant_id)

    artifacts = list(
        db.execute(query.limit(batch_size)).scalars()
    )

    if not artifacts:
        return stats

    base_upload_dir = Path(settings.chat_upload_dir).resolve()

    files_to_delete: list[tuple[Path, Artifact]] = []
    for artifact in artifacts:
        uri = artifact.uri
        if uri and not uri.startswith(("http://", "https://", "s3://", "gs://", "az://")):
            file_path = base_upload_dir / uri
            if file_path.exists():
                files_to_delete.append((file_path, artifact))

    if dry_run:
        for file_path, artifact in files_to_delete:
            try:
                size = file_path.stat().st_size
                stats["files_deleted"] += 1
                stats["bytes_freed"] += size
            except Exception as e:
                stats["errors"].append(f"{file_path}: {e}")
        stats["artifacts_deleted"] = len(artifacts)
        return stats

    artifact_ids_to_delete = [a.id for a in artifacts]
    
    try:
        db.execute(
            Artifact.__table__.delete().where(Artifact.id.in_(artifact_ids_to_delete))
        )
        db.commit()
        logger.info(
            "Deleted %d old artifact records from database (older than %d days)",
            len(artifact_ids_to_delete),
            days,
        )
    except Exception as e:
        db.rollback()
        stats["errors"].append(f"Database commit failed: {e}")
        logger.error("Failed to delete old artifact records: %s", e)
        return stats

    stats["artifacts_deleted"] = len(artifact_ids_to_delete)

    for file_path, artifact in files_to_delete:
        try:
            size = file_path.stat().st_size
            file_path.unlink()
            stats["files_deleted"] += 1
            stats["bytes_freed"] += size
        except Exception as e:
            error_msg = f"{artifact.uri}: {e}"
            stats["errors"].append(error_msg)
            stats["failed_file_deletions"].append({
                "artifact_id": str(artifact.id),
                "uri": artifact.uri,
                "error": str(e),
            })

    logger.info(
        "Cleaned up %d old artifacts (older than %d days, %d files, %d errors)",
        stats["artifacts_deleted"],
        days,
        stats["files_deleted"],
        len(stats["errors"]),
    )

    return stats


__all__ = [
    "cleanup_expired_artifacts",
    "cleanup_old_artifacts",
    "get_artifact_expiry_date",
    "mark_artifacts_for_expiry",
]
