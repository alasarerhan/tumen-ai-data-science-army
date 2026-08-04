"""API routes for agent discovery service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from platform_api.authz.dependencies import require_workspace_member
from platform_api.discovery.agent_discovery import AgentDiscoveryService

router = APIRouter(prefix="/v1/discovery", tags=["discovery"])


class SearchRequest(BaseModel):
    query: str
    filters: dict[str, Any] | None = None
    top_k: int = 20


class RecommendRequest(BaseModel):
    workflow_spec: dict[str, Any]
    top_k: int = 5


@router.post("/search")
async def search_agents(
    body: SearchRequest,
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    service = AgentDiscoveryService()

    results = await service.search(
        query=body.query,
        filters=body.filters,
        top_k=body.top_k,
    )

    return {
        "query": body.query,
        "results": results,
        "total": len(results),
    }


@router.get("/browse")
async def browse_agents(
    category: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    capabilities: str | None = Query(default=None),
    cost_tier: str | None = Query(default=None),
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    service = AgentDiscoveryService()

    tag_list = tags.split(",") if tags else None
    capability_list = capabilities.split(",") if capabilities else None

    results = await service.browse(
        category=category,
        tags=tag_list,
        capabilities=capability_list,
        cost_tier=cost_tier,
    )

    return {
        "filters": {
            "category": category,
            "tags": tag_list,
            "capabilities": capability_list,
            "cost_tier": cost_tier,
        },
        "results": results,
        "total": len(results),
    }


@router.post("/recommend")
async def recommend_agents(
    body: RecommendRequest,
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    service = AgentDiscoveryService()

    recommendations = await service.recommend(
        workflow_spec=body.workflow_spec,
        top_k=body.top_k,
    )

    return {
        "recommendations": recommendations,
        "total": len(recommendations),
    }


@router.get("/categories")
async def get_categories(
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    service = AgentDiscoveryService()

    categories = await service.get_categories()

    return {
        "categories": categories,
        "total": len(categories),
    }


@router.post("/index", status_code=200)
async def index_agents(
    context: dict = Depends(require_workspace_member),
) -> dict[str, Any]:
    service = AgentDiscoveryService()

    count = await service.index_agents()

    return {
        "indexed": count,
        "status": "success" if count > 0 else "no_agents_indexed",
    }
