from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class WorkflowSpecStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class CreateWorkflowSpecRequest(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=150)
    spec: dict = Field(default_factory=dict)
    publish: bool = False


class WorkflowSpecResponseItem(BaseModel):
    id: str
    workspace_id: str
    tenant_id: str
    name: str
    version: int
    status: WorkflowSpecStatus
    spec: dict
    validation_summary: dict
    created_at: str | None = None
    updated_at: str | None = None


class WorkflowSpecPublishResponse(BaseModel):
    id: str
    name: str
    version: int
    status: WorkflowSpecStatus
    validation_summary: dict | None = None


# Keep backward-compat alias
ListWorkflowSpecsResponseItem = WorkflowSpecResponseItem
