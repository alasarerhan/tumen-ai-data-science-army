from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RoleRequirement = Literal["member", "workspace_admin", "tenant_admin", "system"]
RiskLevel = Literal["low", "medium", "high"]


class PlatformResourceDescriptor(BaseModel):
    resource_key: str
    label: str
    scope: Literal["user", "workspace", "tenant", "admin", "system"]
    backing_source: str
    queryable_fields: list[str] = Field(default_factory=list)
    filterable_fields: list[str] = Field(default_factory=list)
    sortable_fields: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    default_limit: int = 20
    freshness: str = "request-time"
    required_role: RoleRequirement = "member"
    redacted_fields: list[str] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)
    canonical_ui: str | None = None
    owner_module: str
    resolver: str | None = None
    tags: list[str] = Field(default_factory=list)
    not_exposed_reason: str | None = None


class NonQueryableSurface(BaseModel):
    surface_key: str
    reason: str
    owner_module: str


class PlatformProvenance(BaseModel):
    resource_key: str
    resolver: str
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    filters: dict[str, Any] = Field(default_factory=dict)
    redactions: list[str] = Field(default_factory=list)


class PlatformEntityRef(BaseModel):
    resource_key: str
    entity_id: str
    label: str
    href: str | None = None


class PlatformRelationship(BaseModel):
    source: PlatformEntityRef
    target: PlatformEntityRef
    relationship_type: str


class PlatformQuerySection(BaseModel):
    resource_key: str
    label: str
    status: Literal["ok", "empty", "access_denied", "not_configured", "error"]
    message: str | None = None
    columns: list[str] = Field(default_factory=list)
    records: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    links: list[dict[str, str]] = Field(default_factory=list)
    relationships: list[PlatformRelationship] = Field(default_factory=list)
    provenance: PlatformProvenance


class PlatformQueryPlan(BaseModel):
    query: str
    resource_keys: list[str]
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 20


class PlatformActionPlan(BaseModel):
    action_name: str
    resource_key: str
    risk_level: RiskLevel
    confirmation_required: bool
    allowed: bool
    summary: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    missing_arguments: list[str] = Field(default_factory=list)
    denial_reason: str | None = None


class PlatformActionResult(BaseModel):
    status: Literal["planned", "executed", "denied", "missing_arguments", "conflict", "error"]
    action_name: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    audit_id: str | None = None


class PlatformQueryResult(BaseModel):
    type: Literal["platform_query_result"] = "platform_query_result"
    summary: str
    query: str
    plan: PlatformQueryPlan
    sections: list[PlatformQuerySection] = Field(default_factory=list)
    action_plan: PlatformActionPlan | None = None


class PlatformQueryRequest(BaseModel):
    workspace_id: str
    query: str = Field(min_length=1, max_length=20_000)
    resource_keys: list[str] | None = None
    limit: int = Field(default=20, ge=1, le=100)
    filters: dict[str, Any] = Field(default_factory=dict)


class PlatformActionPlanRequest(BaseModel):
    workspace_id: str
    action_name: str | None = Field(default=None, min_length=1, max_length=120)
    query: str | None = Field(default=None, min_length=1, max_length=20_000)
    arguments: dict[str, Any] = Field(default_factory=dict)


class PlatformActionExecuteRequest(PlatformActionPlanRequest):
    action_name: str = Field(min_length=1, max_length=120)
    confirmed: bool = False
