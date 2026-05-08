from __future__ import annotations

from sqlalchemy import text

from fastapi import APIRouter, Response
from platform_api.db.session import get_db

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/health")
def health_alias() -> dict:
    return healthz()


@router.get("/ready")
def readiness(response: Response) -> dict:
    result = {"status": "ok", "checks": {}}
    
    db = next(get_db())
    try:
        db.execute(text("SELECT 1"))
        result["checks"]["database"] = "ok"
    except Exception as e:
        result["checks"]["database"] = f"failed: {str(e)[:100]}"
        result["status"] = "degraded"
        response.status_code = 503
    
    return result
