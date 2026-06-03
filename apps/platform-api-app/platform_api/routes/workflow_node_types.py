from __future__ import annotations

from fastapi import APIRouter, Depends

from platform_api.authz.dependencies import require_workspace_member
from platform_api.services.workflow_node_catalog_service import get_workflow_node_catalog

router = APIRouter(prefix="/v1/workflow-node-types", tags=["workflow-node-types"])


@router.get("")
async def list_workflow_node_types(
    workspace_id: str,
    context: dict = Depends(require_workspace_member),
) -> dict:
    return {
        "workspace_id": str(context["workspace"].id),
        "items": get_workflow_node_catalog(),
    }
