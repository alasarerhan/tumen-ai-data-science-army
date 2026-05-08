from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/errors", tags=["errors"])


class FrontendErrorReport(BaseModel):
    component_stack: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    message: str = Field(min_length=1, max_length=4000)
    name: str = Field(default="Error", min_length=1, max_length=200)
    route: str | None = Field(default=None, max_length=500)
    source: str = Field(default="app", min_length=1, max_length=50)
    stack: str | None = None
    user_agent: str | None = Field(default=None, max_length=1000)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def capture_frontend_error(
    body: FrontendErrorReport,
    response: Response,
) -> dict:
    logger.error(
        "frontend_error_report source=%s route=%s name=%s message=%s",
        body.source,
        body.route or "-",
        body.name,
        body.message,
        extra={
            "frontend_error": {
                "component_stack": body.component_stack,
                "context": body.context,
                "message": body.message,
                "name": body.name,
                "route": body.route,
                "source": body.source,
                "stack": body.stack,
                "user_agent": body.user_agent,
            }
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return {"success": True}
