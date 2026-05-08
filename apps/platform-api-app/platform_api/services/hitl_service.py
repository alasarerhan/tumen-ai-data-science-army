from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from platform_api.core.service_errors import ConflictError, NotFoundError
from platform_api.db.models import HitlApproval, HitlApprovalStatus
from platform_api.db.tenant_query import TenantQuery

logger = logging.getLogger(__name__)


def _parse_uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
    return TenantQuery._parse_uuid(value, label)


def _normalize_hitl_not_found_error(exc: Exception) -> Exception:
    if getattr(exc, "status_code", None) == 404 and getattr(exc, "detail", None) == "HitlApproval not found":
        return NotFoundError("HITL approval not found")
    return exc


def list_hitl_approvals(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    status: str | None = None,
) -> list[HitlApproval]:
    q = select(HitlApproval).where(HitlApproval.workspace_id == workspace_id)
    if status:
        q = q.where(HitlApproval.status == status)
    q = q.order_by(HitlApproval.created_at.desc())
    return list(db.execute(q).scalars())


def get_hitl_approval(db: Session, *, approval_id: uuid.UUID, workspace_id: uuid.UUID) -> HitlApproval:
    """Get a HITL approval by ID, ensuring it belongs to the specified workspace.

    Security: workspace_id filter is applied IN the query (not post-fetch)
    to prevent IDOR vulnerabilities.
    """
    parsed_approval_id = _parse_uuid(approval_id, "approval_id")
    try:
        return TenantQuery(db, HitlApproval).for_workspace(workspace_id).get(parsed_approval_id)
    except Exception as exc:
        raise _normalize_hitl_not_found_error(exc) from exc


def create_hitl_approval(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: uuid.UUID,
    workflow_run_id: uuid.UUID | None,
    step_key: str,
    payload: dict | None = None,
    created_by_user_id: uuid.UUID | None = None,
    expires_hours: int = 48,
) -> HitlApproval:
    item = HitlApproval(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        workflow_run_id=workflow_run_id,
        step_key=step_key,
        payload_json=json.dumps(payload) if payload else None,
        status=HitlApprovalStatus.pending,
        created_by_user_id=created_by_user_id,
        expires_at=datetime.now(UTC) + timedelta(hours=expires_hours),
    )
    db.add(item)
    db.flush()
    return item


def approve_hitl(
    db: Session,
    *,
    item: HitlApproval,
    reviewer_user_id: uuid.UUID,
    comment: str | None = None,
) -> HitlApproval:
    if item.created_by_user_id == reviewer_user_id:
        raise ConflictError("Approval creator cannot approve their own request")
    now = datetime.now(UTC)
    result = db.execute(
        update(HitlApproval)
        .where(
            HitlApproval.id == item.id,
            HitlApproval.status == HitlApprovalStatus.pending,
        )
        .values(
            status=HitlApprovalStatus.approved,
            reviewer_user_id=reviewer_user_id,
            comment=comment,
            reviewed_at=now,
            updated_at=now,
        )
    )
    db.flush()
    if result.rowcount == 0:
        db.refresh(item)
        logger.warning(
            "HITL approval race condition detected: approval_id=%s, current_status=%s, attempted_by_user=%s",
            item.id, item.status, reviewer_user_id,
        )
        raise ConflictError(
            f"Approval already in state: {item.status}. Concurrent modification detected."
        )
    db.refresh(item)
    return item


def reject_hitl(
    db: Session,
    *,
    item: HitlApproval,
    reviewer_user_id: uuid.UUID,
    reason: str | None = None,
) -> HitlApproval:
    if item.created_by_user_id == reviewer_user_id:
        raise ConflictError("Approval creator cannot reject their own request")
    now = datetime.now(UTC)
    result = db.execute(
        update(HitlApproval)
        .where(
            HitlApproval.id == item.id,
            HitlApproval.status == HitlApprovalStatus.pending,
        )
        .values(
            status=HitlApprovalStatus.rejected,
            reviewer_user_id=reviewer_user_id,
            comment=reason,
            reviewed_at=now,
            updated_at=now,
        )
    )
    db.flush()
    if result.rowcount == 0:
        db.refresh(item)
        logger.warning(
            "HITL approval race condition detected: approval_id=%s, current_status=%s, attempted_by_user=%s",
            item.id, item.status, reviewer_user_id,
        )
        raise ConflictError(
            f"Approval already in state: {item.status}. Concurrent modification detected."
        )
    db.refresh(item)
    return item
