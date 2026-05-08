from __future__ import annotations

from pydantic import BaseModel, Field


class CreateArtifactRequest(BaseModel):
    workspace_id: str
    workflow_run_id: str | None = None
    kind: str = Field(min_length=2, max_length=100)
    uri: str = Field(min_length=3)
