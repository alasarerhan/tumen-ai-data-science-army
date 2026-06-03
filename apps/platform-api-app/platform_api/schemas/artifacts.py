from __future__ import annotations

from pydantic import BaseModel, Field


class CreateArtifactRequest(BaseModel):
    workspace_id: str
    workflow_run_id: str | None = None
    kind: str = Field(min_length=2, max_length=100)
    uri: str = Field(min_length=3)
    produced_by_node_id: str | None = Field(default=None, max_length=150)
    parent_artifact_ids: list[str] = Field(default_factory=list)
