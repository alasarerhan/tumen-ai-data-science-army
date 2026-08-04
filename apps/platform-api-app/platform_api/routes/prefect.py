from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from platform_api.auth.dependencies import get_principal
from platform_api.auth.models import Principal
from platform_api.db.session import get_db
from platform_api.schemas.runs import CreateHelloRunRequest
from platform_api.services.identity_service import get_or_create_user
from platform_api.services.run_orchestration_service import (
    create_orchestration_run_id,
    read_orchestration_run,
)
from platform_api.services.run_service import (
    create_workflow_run_record,
    get_workspace_for_member,
    list_workflow_runs_for_workspace,
    update_workflow_run_status,
)

router = APIRouter(prefix="/v1/prefect", tags=["prefect", "deprecated"])

DEPRECATION_DATE = "2025-06-01"
SUNSET_DATE = "2025-12-01"
DEPRECATION_LINK = "https://docs.example.com/api/migration/prefect-to-langgraph"


def _add_deprecation_headers(response: JSONResponse) -> JSONResponse:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = SUNSET_DATE
    response.headers["Link"] = f'<{DEPRECATION_LINK}>; rel="deprecation"; type="text/html"'
    return response


@router.post("/hello-runs")
async def create_hello_run(
    payload: CreateHelloRunRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> JSONResponse:
    user = get_or_create_user(db, principal)
    workspace = get_workspace_for_member(
        db,
        workspace_id=payload.workspace_id,
        user_id=user.id,
    )

    effective_parameters = {"requested_by": principal.sub, **payload.parameters}
    flow_run_id = await create_orchestration_run_id(
        flow_key="hello",
        parameters=effective_parameters,
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        tenant_id=str(workspace.tenant_id),
    )

    run_record = create_workflow_run_record(
        db,
        tenant_id=workspace.tenant_id,
        workspace_id=workspace.id,
        user_id=user.id,
        flow_key="hello",
        prefect_flow_run_id=flow_run_id,
        parameters=effective_parameters,
    )
    db.commit()
    response = JSONResponse(
        content={
            "id": str(run_record.id),
            "flow_run_id": flow_run_id,
            "workspace_id": str(workspace.id),
            "tenant_id": str(workspace.tenant_id),
            "status": run_record.status,
            "deprecated": True,
            "deprecation_message": f"This endpoint is deprecated and will be removed on {SUNSET_DATE}. Migrate to /v1/runs endpoint.",
            "migration_guide": DEPRECATION_LINK,
        }
    )
    return _add_deprecation_headers(response)


@router.get("/flow-runs/{flow_run_id}")
async def read_flow_run(
    flow_run_id: str,
    workspace_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> JSONResponse:
    user = get_or_create_user(db, principal)
    workspace = get_workspace_for_member(db, workspace_id=workspace_id, user_id=user.id)

    local_run_candidates = list_workflow_runs_for_workspace(db, workspace_id=workspace.id)
    if not any(run.prefect_flow_run_id == flow_run_id for run in local_run_candidates):
        raise HTTPException(status_code=404, detail="Flow run not found in workspace")

    result = await read_orchestration_run(flow_run_id)

    state = result.get("state", {})
    update_workflow_run_status(
        db,
        prefect_flow_run_id=flow_run_id,
        status_name=state.get("name"),
        start_time=result.get("start_time"),
        end_time=result.get("end_time"),
    )
    db.commit()

    result["deprecated"] = True
    result["deprecation_message"] = (
        f"This endpoint is deprecated and will be removed on {SUNSET_DATE}. Migrate to /v1/runs endpoint."
    )
    result["migration_guide"] = DEPRECATION_LINK

    response = JSONResponse(content=result)
    return _add_deprecation_headers(response)
