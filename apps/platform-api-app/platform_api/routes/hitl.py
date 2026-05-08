from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.authz.dependencies import _get_workspace_and_membership, require_workspace_member
from platform_api.authz.policy import can_admin_workspace
from platform_api.db.models import HitlApproval
from platform_api.db.session import get_db
from platform_api.services.hitl_service import (
    approve_hitl,
    create_hitl_approval,
    get_hitl_approval,
    list_hitl_approvals,
    reject_hitl,
)

router = APIRouter(prefix="/v1/hitl", tags=["hitl"])


def _hitl_to_dict(item: HitlApproval) -> dict:
    return {
        "id": str(item.id),
        "workspace_id": str(item.workspace_id),
        "tenant_id": str(item.tenant_id),
        "workflow_run_id": str(item.workflow_run_id) if item.workflow_run_id else None,
        "step_key": item.step_key,
        "payload": json.loads(item.payload_json) if item.payload_json else {},
        "status": item.status,
        "comment": item.comment,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.get("")
async def list_approvals(
    workspace_id: str,
    status: str | None = None,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    items = list_hitl_approvals(db, workspace_id=workspace.id, status=status)
    return {"items": [_hitl_to_dict(i) for i in items]}


@router.get("/{approval_id}")
async def get_approval(
    approval_id: str,
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    try:
        aid = uuid.UUID(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid approval_id") from exc
    item = get_hitl_approval(db, approval_id=aid, workspace_id=workspace.id)
    return _hitl_to_dict(item)


class CreateApprovalRequest(BaseModel):
    workspace_id: str
    workflow_run_id: str | None = None
    step_key: str
    payload: dict = {}
    expires_hours: int = 48


@router.post("", status_code=201)
async def create_approval(
    body: CreateApprovalRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    context = _get_workspace_and_membership(body.workspace_id, principal, db)
    workspace = context["workspace"]
    user = context["user"]
    run_id = uuid.UUID(body.workflow_run_id) if body.workflow_run_id else None
    item = create_hitl_approval(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        workflow_run_id=run_id,
        step_key=body.step_key,
        payload=body.payload or None,
        created_by_user_id=user.id,
        expires_hours=body.expires_hours,
    )
    db.commit()
    db.refresh(item)
    return _hitl_to_dict(item)


class ApproveRequest(BaseModel):
    workspace_id: str
    comment: str | None = None


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: str,
    body: ApproveRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    context = _get_workspace_and_membership(body.workspace_id, principal, db)
    if not can_admin_workspace(context["membership"].role):
        raise HTTPException(status_code=403, detail="Workspace admin or owner role required")
    workspace = context["workspace"]
    user = context["user"]
    try:
        aid = uuid.UUID(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid approval_id") from exc
    item = get_hitl_approval(db, approval_id=aid, workspace_id=workspace.id)
    item = approve_hitl(db, item=item, reviewer_user_id=user.id, comment=body.comment)
    db.commit()
    db.refresh(item)
    return _hitl_to_dict(item)


class RejectRequest(BaseModel):
    workspace_id: str
    reason: str | None = None


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: str,
    body: RejectRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    context = _get_workspace_and_membership(body.workspace_id, principal, db)
    if not can_admin_workspace(context["membership"].role):
        raise HTTPException(status_code=403, detail="Workspace admin or owner role required")
    workspace = context["workspace"]
    user = context["user"]
    try:
        aid = uuid.UUID(approval_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid approval_id") from exc
    item = get_hitl_approval(db, approval_id=aid, workspace_id=workspace.id)
    item = reject_hitl(db, item=item, reviewer_user_id=user.id, reason=body.reason)
    db.commit()
    db.refresh(item)
    return _hitl_to_dict(item)
