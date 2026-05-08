from __future__ import annotations

from pydantic import BaseModel, Field


class CreateHelloRunRequest(BaseModel):
    workspace_id: str
    parameters: dict = Field(default_factory=dict)
