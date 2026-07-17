"""API routes for workflow versioning and canary deployments."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis import Redis
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_workspace_admin, require_workspace_member
from platform_api.core.config import settings
from platform_api.db.session import get_db
from platform_api.services.workflow_service import get_workflow_spec_for_workspace
from platform_api.versioning.models import CanaryDeployment, WorkflowVersion
from platform_api.versioning.version_manager import WorkflowVersionManager

router = APIRouter(prefix="/v1/versioning", tags=["versioning"])


class CreateVersionRequest(BaseModel):
    workflow_id: str
    workflow_spec: Dict[str, Any]
    changelog: str = ""


class DeployVersionRequest(BaseModel):
    strategy: str = "canary"


class RollbackRequest(BaseModel):
    target_version: int
    reason: str = "Manual rollback"


class CheckMetricsRequest(BaseModel):
    metrics: Dict[str, Any]


def _get_redis() -> Optional[Redis]:
    if settings.agent_cache_redis_url:
        return Redis.from_url(settings.agent_cache_redis_url)
    return None


def _require_scoped_workflow_spec(
    db: Session,
    *,
    workflow_id: str,
    workspace_id,
    user_id: uuid.UUID,
):
    try:
        return get_workflow_spec_for_workspace(
            db,
            workflow_id=workflow_id,
            workspace_id=str(workspace_id),
            user_id=user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Workflow spec not found") from exc


def _require_scoped_version(
    db: Session,
    *,
    version_id: str,
    workspace_id,
    user_id: uuid.UUID,
) -> WorkflowVersion:
    version = db.get(WorkflowVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    _require_scoped_workflow_spec(
        db,
        workflow_id=version.workflow_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return version


def _require_scoped_deployment(
    db: Session,
    *,
    deployment_id: str,
    workspace_id,
    user_id: uuid.UUID,
) -> CanaryDeployment:
    deployment = db.get(CanaryDeployment, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="Canary deployment not found")
    _require_scoped_workflow_spec(
        db,
        workflow_id=deployment.workflow_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    return deployment


@router.post("/versions", status_code=201)
async def create_version(
    body: CreateVersionRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = context["user"]
    workspace = context["workspace"]
    redis = _get_redis()
    workflow_spec = _require_scoped_workflow_spec(
        db,
        workflow_id=body.workflow_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    
    manager = WorkflowVersionManager(db, redis)
    
    try:
        version_id = await manager.create_version(
            workflow_id=str(workflow_spec.id),
            workflow_spec=body.workflow_spec,
            changelog=body.changelog,
            created_by=str(user.id),
        )
        
        version = await manager._get_version(version_id)
        
        return {
            "id": version_id,
            "workflow_id": str(workflow_spec.id),
            "version": version.version if version else 1,
            "status": "draft",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/versions/{version_id}/deploy", status_code=200)
async def deploy_version(
    version_id: str,
    body: DeployVersionRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = context["user"]
    workspace = context["workspace"]
    redis = _get_redis()
    _require_scoped_version(db, version_id=version_id, workspace_id=workspace.id, user_id=user.id)
    
    manager = WorkflowVersionManager(db, redis)
    
    try:
        result = await manager.deploy_version(
            version_id=version_id,
            strategy=body.strategy,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deployments/{deployment_id}/advance", status_code=200)
async def advance_canary(
    deployment_id: str,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = context["user"]
    workspace = context["workspace"]
    redis = _get_redis()
    _require_scoped_deployment(
        db,
        deployment_id=deployment_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    
    manager = WorkflowVersionManager(db, redis)
    
    try:
        result = await manager.advance_canary(deployment_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/workflows/{workflow_id}/rollback", status_code=200)
async def rollback_workflow(
    workflow_id: str,
    body: RollbackRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = context["user"]
    workspace = context["workspace"]
    redis = _get_redis()
    _require_scoped_workflow_spec(
        db,
        workflow_id=workflow_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    
    manager = WorkflowVersionManager(db, redis)
    
    try:
        result = await manager.rollback(
            workflow_id=workflow_id,
            target_version=body.target_version,
            reason=body.reason,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deployments/{deployment_id}/check-metrics", status_code=200)
async def check_rollback_triggers(
    deployment_id: str,
    body: CheckMetricsRequest,
    context: dict = Depends(require_workspace_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = context["user"]
    workspace = context["workspace"]
    redis = _get_redis()
    _require_scoped_deployment(
        db,
        deployment_id=deployment_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    
    manager = WorkflowVersionManager(db, redis)
    
    try:
        result = await manager.check_rollback_triggers(
            deployment_id=deployment_id,
            metrics=body.metrics,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workflows/{workflow_id}/versions")
async def get_version_history(
    workflow_id: str,
    limit: int = 10,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    user = context["user"]
    workspace = context["workspace"]
    redis = _get_redis()
    _require_scoped_workflow_spec(
        db,
        workflow_id=workflow_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    
    manager = WorkflowVersionManager(db, redis)
    
    versions = await manager.get_version_history(
        workflow_id=workflow_id,
        limit=limit,
    )
    
    return {"versions": versions}
