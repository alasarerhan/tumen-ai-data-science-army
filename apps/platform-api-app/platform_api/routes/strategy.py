from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from platform_api.authz.dependencies import require_workspace_member
from platform_api.db.session import get_db
from platform_api.services.strategy_service import generate_workspace_strategy_report

router = APIRouter(prefix="/v1/strategy", tags=["strategy"])


@router.get("/reports/generate")
async def generate_report(
    workspace_id: str,
    run_id: str | None = None,
    context: dict = Depends(require_workspace_member),
    db: Session = Depends(get_db),
) -> dict:
    workspace = context["workspace"]
    report = await generate_workspace_strategy_report(
        db,
        tenant_id=str(workspace.tenant_id),
        workspace_id=str(workspace.id),
        run_id=run_id,
    )
    return report
