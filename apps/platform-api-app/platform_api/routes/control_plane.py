from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.authz.dependencies import _get_workspace_and_membership, require_workspace_member
from platform_api.control_plane.actions import execute_action, plan_action, plan_action_from_text
from platform_api.control_plane.catalog import get_non_queryable_surfaces, get_platform_catalog
from platform_api.control_plane.policies import ControlPlaneContext, policy_engine
from platform_api.control_plane.query import execute_platform_query, plan_query_from_text
from platform_api.control_plane.schemas import (
    PlatformActionExecuteRequest,
    PlatformActionPlanRequest,
    PlatformQueryRequest,
)
from platform_api.db.session import get_db

router = APIRouter(prefix="/v1/control-plane", tags=["control-plane"])


@router.get("/catalog")
async def get_catalog(
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    ctx = ControlPlaneContext(
        db=db,
        user=context["user"],
        workspace=context["workspace"],
        membership=context["membership"],
    )
    visible = []
    for descriptor in get_platform_catalog():
        if policy_engine.can_access_descriptor(ctx, descriptor):
            visible.append(descriptor.model_dump(mode="json"))
    return {
        "items": visible,
        "non_queryable": [item.model_dump(mode="json") for item in get_non_queryable_surfaces()],
    }


@router.post("/query")
async def query_control_plane(
    body: PlatformQueryRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    context = _get_workspace_and_membership(body.workspace_id, principal, db)
    ctx = ControlPlaneContext(
        db=db,
        user=context["user"],
        workspace=context["workspace"],
        membership=context["membership"],
    )
    plan = plan_query_from_text(
        body.query,
        resource_keys=body.resource_keys,
        filters=body.filters,
        limit=body.limit,
    )
    result = execute_platform_query(ctx, plan)
    return result.model_dump(mode="json")


@router.post("/actions/plan")
async def plan_control_plane_action(
    body: PlatformActionPlanRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    context = _get_workspace_and_membership(body.workspace_id, principal, db)
    ctx = ControlPlaneContext(
        db=db,
        user=context["user"],
        workspace=context["workspace"],
        membership=context["membership"],
    )
    if body.action_name:
        result = plan_action(ctx, action_name=body.action_name, arguments=body.arguments)
    elif body.query:
        text_plan = plan_action_from_text(body.query)
        if text_plan is None:
            return {
                "action_name": "none",
                "resource_key": "platform.overview",
                "risk_level": "low",
                "confirmation_required": False,
                "allowed": False,
                "summary": "No governed platform action could be planned from the request.",
                "arguments": {},
                "missing_arguments": [],
                "denial_reason": "No catalog-backed action intent was detected.",
            }
        merged_arguments = {**text_plan.arguments, **body.arguments}
        result = plan_action(ctx, action_name=text_plan.action_name, arguments=merged_arguments)
    else:
        return {
            "action_name": "none",
            "resource_key": "platform.overview",
            "risk_level": "low",
            "confirmation_required": False,
            "allowed": False,
            "summary": "No action_name or natural-language query was provided.",
            "arguments": {},
            "missing_arguments": [],
            "denial_reason": "Provide action_name or query.",
        }
    return result.model_dump(mode="json")


@router.post("/actions/execute")
async def execute_control_plane_action(
    body: PlatformActionExecuteRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> dict:
    context = _get_workspace_and_membership(body.workspace_id, principal, db)
    ctx = ControlPlaneContext(
        db=db,
        user=context["user"],
        workspace=context["workspace"],
        membership=context["membership"],
    )
    result = await execute_action(
        ctx,
        action_name=body.action_name,
        arguments=body.arguments,
        confirmed=body.confirmed,
    )
    return result.model_dump(mode="json")
