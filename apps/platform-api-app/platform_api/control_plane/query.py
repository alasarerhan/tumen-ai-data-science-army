from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select

from platform_api.control_plane.catalog import (
    catalog_resource_keys,
    get_descriptor,
    get_platform_catalog,
)
from platform_api.control_plane.policies import ControlPlaneContext, policy_engine
from platform_api.control_plane.schemas import (
    PlatformActionPlan,
    PlatformEntityRef,
    PlatformProvenance,
    PlatformQueryPlan,
    PlatformQueryResult,
    PlatformQuerySection,
    PlatformRelationship,
)
from platform_api.core.config import settings
from platform_api.db.models import (
    AgentExecutionTrace,
    Artifact,
    AuditLog,
    ChatSession,
    ChatUpload,
    DataSource,
    HitlApproval,
    OutboxDlq,
    ScheduledJob,
    User,
    WorkflowNodeExecution,
    WorkflowRun,
    WorkflowSignalEvent,
    WorkflowSpec,
    Workspace,
    WorkspaceMembership,
)
from platform_api.services.modelops_service import get_modelops_summary
from platform_api.services.workflow_service import build_workflow_validation_summary

Resolver = Callable[[ControlPlaneContext, PlatformQueryPlan, str], PlatformQuerySection]

PLATFORM_TERMS = {
    "platform",
    "application",
    "app",
    "system",
    "workspace",
    "uygulama",
    "sistem",
    "kontrol",
    "durum",
    "state",
    "status",
    "task",
    "tasks",
    "gorev",
}

ANALYTIC_CREATION_TERMS = {
    "create workflow",
    "build workflow",
    "generate workflow",
    "workflow olustur",
    "pipeline olustur",
    "workflow tasarla",
}


def plan_query_from_text(
    query: str,
    *,
    resource_keys: list[str] | None = None,
    filters: dict[str, Any] | None = None,
    limit: int = 20,
) -> PlatformQueryPlan:
    if resource_keys:
        selected = [key for key in resource_keys if key in catalog_resource_keys()]
        return PlatformQueryPlan(
            query=query, resource_keys=selected, filters=filters or {}, limit=limit
        )

    normalized = _normalize(query)
    if any(term in normalized for term in ANALYTIC_CREATION_TERMS):
        return PlatformQueryPlan(query=query, resource_keys=[], filters=filters or {}, limit=limit)

    broad_query = _is_broad_platform_query(normalized)
    if broad_query:
        return PlatformQueryPlan(
            query=query,
            resource_keys=[
                "platform.overview",
                "configuration.settings",
                "workflows",
                "runs",
                "data_sources",
                "artifacts",
                "release.docs",
            ],
            filters=filters or {},
            limit=limit,
        )

    scored: list[tuple[int, str]] = []
    for descriptor in get_platform_catalog():
        score = 0
        searchable = [
            descriptor.resource_key,
            descriptor.label,
            *descriptor.tags,
            *descriptor.queryable_fields,
        ]
        for token in searchable:
            normalized_token = _normalize(token)
            if normalized_token and normalized_token in normalized:
                score += (
                    3
                    if "." in descriptor.resource_key
                    and normalized_token == descriptor.resource_key
                    else 1
                )
        for part in descriptor.resource_key.split("."):
            if part and part in normalized:
                score += 1
        if score > 0:
            scored.append((score, descriptor.resource_key))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [key for _score, key in scored[:6]]
    return PlatformQueryPlan(
        query=query, resource_keys=selected, filters=filters or {}, limit=limit
    )


def should_route_to_control_plane(query: str) -> bool:
    plan = plan_query_from_text(query)
    return bool(plan.resource_keys)


def execute_platform_query(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan
) -> PlatformQueryResult:
    sections: list[PlatformQuerySection] = []
    for resource_key in plan.resource_keys:
        descriptor = get_descriptor(resource_key)
        if descriptor is None:
            continue

        if not policy_engine.can_access_descriptor(ctx, descriptor):
            sections.append(
                _section(
                    resource_key=resource_key,
                    label=descriptor.label,
                    status="access_denied",
                    message=f"{descriptor.label} requires {descriptor.required_role} access.",
                    resolver=descriptor.resolver or "none",
                    redactions=descriptor.redacted_fields,
                    filters=plan.filters,
                )
            )
            continue

        if descriptor.resolver is None:
            sections.append(
                _section(
                    resource_key=resource_key,
                    label=descriptor.label,
                    status="not_configured",
                    message=descriptor.not_exposed_reason
                    or "No resolver is configured for this resource yet.",
                    resolver="none",
                    redactions=descriptor.redacted_fields,
                    filters=plan.filters,
                )
            )
            continue

        resolver = RESOLVERS.get(descriptor.resolver)
        if resolver is None:
            sections.append(
                _section(
                    resource_key=resource_key,
                    label=descriptor.label,
                    status="not_configured",
                    message=f"Resolver '{descriptor.resolver}' is not registered.",
                    resolver=descriptor.resolver,
                    redactions=descriptor.redacted_fields,
                    filters=plan.filters,
                )
            )
            continue

        try:
            sections.append(resolver(ctx, plan, resource_key))
        except Exception as exc:  # noqa: BLE001
            sections.append(
                _section(
                    resource_key=resource_key,
                    label=descriptor.label,
                    status="error",
                    message=str(exc),
                    resolver=descriptor.resolver,
                    redactions=descriptor.redacted_fields,
                    filters=plan.filters,
                )
            )

    if not sections:
        summary = "No matching platform resources were found in the control-plane catalog."
    else:
        ok_sections = [section for section in sections if section.status == "ok"]
        total_records = sum(len(section.records) for section in ok_sections)
        summary = f"Control plane resolved {len(sections)} resource surface(s) with {total_records} visible record(s)."

    return PlatformQueryResult(summary=summary, query=plan.query, plan=plan, sections=sections)


def attach_action_plan(
    result: PlatformQueryResult, action_plan: PlatformActionPlan | None
) -> PlatformQueryResult:
    if action_plan is None:
        return result
    result.action_plan = action_plan
    result.summary = f"{result.summary} A governed action plan is available."
    return result


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().replace("ı", "i")).strip()


def _is_broad_platform_query(normalized: str) -> bool:
    if any(
        term in normalized
        for term in ["her sey", "herseyi", "tum", "tumu", "everything", "all platform"]
    ):
        return True
    return any(term in normalized for term in PLATFORM_TERMS) and any(
        term in normalized for term in ["status", "durum", "state", "summary", "ozet", "overview"]
    )


def _section(
    *,
    resource_key: str,
    label: str,
    status: str,
    resolver: str,
    message: str | None = None,
    columns: list[str] | None = None,
    records: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    links: list[dict[str, str]] | None = None,
    relationships: list[PlatformRelationship] | None = None,
    redactions: list[str] | None = None,
    filters: dict[str, Any] | None = None,
) -> PlatformQuerySection:
    return PlatformQuerySection(
        resource_key=resource_key,
        label=label,
        status=status,  # type: ignore[arg-type]
        message=message,
        columns=columns or [],
        records=records or [],
        metrics=metrics or {},
        links=links or [],
        relationships=relationships or [],
        provenance=PlatformProvenance(
            resource_key=resource_key,
            resolver=resolver,
            filters=filters or {},
            redactions=redactions or [],
        ),
    )


def _status_for_records(records: list[dict[str, Any]]) -> str:
    return "ok" if records else "empty"


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _first_numeric(payload: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _mask_uri(uri: str) -> str:
    if not uri:
        return uri
    return re.sub(r"(://[^:/@\s]+:)([^@\s]+)(@)", r"\1****\3", uri)


def _safe_data_source_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    safe = dict(metadata)
    safe.pop("password", None)
    safe.pop("secret_value", None)
    if "secret_ref" in safe:
        safe["has_secret"] = True
        safe.pop("secret_ref", None)
    return safe


def _resolve_overview(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    metrics = {
        "workflows": ctx.db.execute(
            select(func.count())
            .select_from(WorkflowSpec)
            .where(WorkflowSpec.workspace_id == ctx.workspace.id)
        ).scalar()
        or 0,
        "runs": ctx.db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.workspace_id == ctx.workspace.id)
        ).scalar()
        or 0,
        "artifacts": ctx.db.execute(
            select(func.count())
            .select_from(Artifact)
            .where(Artifact.workspace_id == ctx.workspace.id)
        ).scalar()
        or 0,
        "data_sources": ctx.db.execute(
            select(func.count())
            .select_from(DataSource)
            .where(DataSource.workspace_id == ctx.workspace.id)
        ).scalar()
        or 0,
        "uploads": ctx.db.execute(
            select(func.count())
            .select_from(ChatUpload)
            .where(ChatUpload.workspace_id == ctx.workspace.id)
        ).scalar()
        or 0,
        "approvals": ctx.db.execute(
            select(func.count())
            .select_from(HitlApproval)
            .where(HitlApproval.workspace_id == ctx.workspace.id)
        ).scalar()
        or 0,
    }
    return _section(
        resource_key=resource_key,
        label="Platform Overview",
        status="ok",
        resolver="overview",
        metrics=metrics,
        records=[
            {"workspace_id": str(ctx.workspace.id), "workspace_name": ctx.workspace.name, **metrics}
        ],
        columns=["workspace_name", *metrics.keys()],
        links=[{"label": "Dashboard", "href": "/dashboard"}],
        filters=plan.filters,
    )


def _resolve_identity(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    records = [
        {
            "user_id": str(ctx.user.id),
            "email": ctx.user.email,
            "workspace_id": str(ctx.workspace.id),
            "workspace_name": ctx.workspace.name,
            "tenant_id": str(ctx.workspace.tenant_id),
            "workspace_role": str(
                ctx.membership.role.value
                if hasattr(ctx.membership.role, "value")
                else ctx.membership.role
            ),
        }
    ]
    return _section(
        resource_key=resource_key,
        label="Current User and Workspace",
        status="ok",
        resolver="identity",
        columns=list(records[0].keys()),
        records=records,
        filters=plan.filters,
    )


def _resolve_configuration(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    records = [
        {
            "deployment_profile": settings.deployment_profile,
            "auth_mode": settings.auth_mode,
            "csrf_enabled": settings.csrf_enabled,
            "artifact_storage_backend": settings.artifact_storage_backend,
            "chat_upload_max_mb": settings.chat_upload_max_mb,
            "data_source_secret_policy": "configured"
            if settings.data_source_secret_key
            else "not_configured",
            "secret_values": "<redacted>",
        }
    ]
    return _section(
        resource_key=resource_key,
        label="Safe Platform Configuration",
        status="ok",
        resolver="configuration",
        columns=list(records[0].keys()),
        records=records,
        links=[{"label": "Settings", "href": "/settings"}],
        redactions=["data_source_secret_key", "openai_api_key", "dev_auth_token"],
        filters=plan.filters,
    )


def _resolve_data_sources(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(DataSource)
            .where(DataSource.workspace_id == ctx.workspace.id)
            .order_by(DataSource.created_at.desc(), DataSource.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = []
    for ds in rows:
        metadata = _json_loads(ds.metadata_json, {})
        records.append(
            {
                "id": str(ds.id),
                "name": ds.name,
                "kind": ds.kind,
                "connection_uri": _mask_uri(ds.connection_uri),
                "metadata": _safe_data_source_metadata(metadata),
                "created_at": _iso(ds.created_at),
                "updated_at": _iso(ds.updated_at),
            }
        )
    return _section(
        resource_key=resource_key,
        label="Data Sources",
        status=_status_for_records(records),
        resolver="data_sources",
        columns=["id", "name", "kind", "connection_uri", "created_at", "updated_at"],
        records=records,
        links=[{"label": "Data Sources", "href": "/data-sources"}],
        redactions=["connection_uri.password", "metadata.secret_ref", "metadata.password"],
        filters=plan.filters,
    )


def _resolve_chat_uploads(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(ChatUpload)
            .where(ChatUpload.workspace_id == ctx.workspace.id)
            .order_by(ChatUpload.created_at.desc(), ChatUpload.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(upload.id),
            "session_id": str(upload.session_id),
            "filename": upload.filename,
            "content_type": upload.content_type,
            "size_bytes": upload.size_bytes,
            "created_at": _iso(upload.created_at),
        }
        for upload in rows
    ]
    return _section(
        resource_key=resource_key,
        label="Chat Uploads",
        status=_status_for_records(records),
        resolver="chat_uploads",
        columns=["filename", "content_type", "size_bytes", "created_at"],
        records=records,
        links=[{"label": "AI Workspace", "href": "/ai-workspace"}],
        filters=plan.filters,
    )


def _resolve_workflows(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(WorkflowSpec)
            .where(WorkflowSpec.workspace_id == ctx.workspace.id)
            .order_by(WorkflowSpec.created_at.desc(), WorkflowSpec.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = []
    for workflow in rows:
        spec = _json_loads(workflow.spec_json, {})
        records.append(
            {
                "id": str(workflow.id),
                "name": workflow.name,
                "version": workflow.version,
                "status": workflow.status,
                "validation_status": build_workflow_validation_summary(
                    spec, workflow_name=workflow.name
                )["status"],
                "created_at": _iso(workflow.created_at),
                "updated_at": _iso(workflow.updated_at),
            }
        )
    return _section(
        resource_key=resource_key,
        label="Workflow Specs",
        status=_status_for_records(records),
        resolver="workflows",
        columns=["name", "version", "status", "validation_status", "created_at", "updated_at"],
        records=records,
        links=[{"label": "Workflows", "href": "/workflows"}],
        filters=plan.filters,
    )


def _resolve_workflow_schedules(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(WorkflowSpec)
            .where(WorkflowSpec.workspace_id == ctx.workspace.id)
            .order_by(WorkflowSpec.created_at.desc(), WorkflowSpec.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records: list[dict[str, Any]] = []
    for workflow in rows:
        spec = _json_loads(workflow.spec_json, {})
        schedule = spec.get("schedule") if isinstance(spec, dict) else None
        triggers = spec.get("triggers") if isinstance(spec, dict) else None
        trigger_schedule = _first_schedule_trigger(triggers)
        schedule_data = schedule if isinstance(schedule, dict) else trigger_schedule
        if not isinstance(schedule_data, dict):
            continue
        cron = schedule_data.get("cron") or schedule_data.get("cron_expression")
        interval = schedule_data.get("interval_seconds")
        enabled = schedule_data.get("enabled")
        if cron is None and interval is None:
            continue
        records.append(
            {
                "workflow_spec_id": str(workflow.id),
                "workflow_name": workflow.name,
                "workflow_version": workflow.version,
                "cron": cron,
                "interval_seconds": interval,
                "timezone": schedule_data.get("timezone", "UTC"),
                "enabled": True if enabled is None else bool(enabled),
                "source": "workflow_spec",
            }
        )
    persisted_jobs = list(
        ctx.db.execute(
            select(ScheduledJob)
            .where(ScheduledJob.job_name.like(f"%{ctx.workspace.id}%"))
            .order_by(ScheduledJob.next_run_at.asc(), ScheduledJob.job_name.asc())
            .limit(plan.limit)
        ).scalars()
    )
    for job in persisted_jobs:
        records.append(
            {
                "workflow_spec_id": None,
                "workflow_name": job.job_name,
                "workflow_version": None,
                "cron": job.cron_expression,
                "interval_seconds": job.interval_seconds,
                "timezone": "UTC",
                "enabled": bool(job.enabled),
                "source": "scheduled_job",
                "last_run_status": job.last_run_status,
                "next_run_at": _iso(job.next_run_at),
            }
        )
    return _section(
        resource_key=resource_key,
        label="Workflow Schedules",
        status=_status_for_records(records),
        resolver="workflow_schedules",
        message=(
            "Shows schedule metadata persisted in workflow specs plus workspace-scoped scheduler jobs when available. "
            "External Prefect deployment connectivity is optional runtime evidence, not a catalog prerequisite."
        ),
        columns=[
            "workflow_name",
            "workflow_version",
            "cron",
            "interval_seconds",
            "timezone",
            "enabled",
            "source",
            "last_run_status",
            "next_run_at",
        ],
        records=records,
        links=[{"label": "Workflows", "href": "/workflows"}],
        filters=plan.filters,
    )


def _resolve_runs(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.workspace_id == ctx.workspace.id)
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(run.id),
            "flow_key": run.flow_key,
            "workflow_spec_id": str(run.workflow_spec_id) if run.workflow_spec_id else None,
            "workflow_version": run.workflow_version,
            "trigger_type": run.trigger_type,
            "status": run.status,
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
            "created_at": _iso(run.created_at),
            "updated_at": _iso(run.updated_at),
        }
        for run in rows
    ]
    return _section(
        resource_key=resource_key,
        label="Workflow Runs",
        status=_status_for_records(records),
        resolver="runs",
        columns=[
            "flow_key",
            "status",
            "workflow_version",
            "trigger_type",
            "created_at",
            "updated_at",
        ],
        records=records,
        links=[{"label": "Runs", "href": "/runs"}],
        filters=plan.filters,
    )


def _resolve_run_nodes(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    stmt = select(WorkflowNodeExecution).where(
        WorkflowNodeExecution.workspace_id == ctx.workspace.id
    )
    run_id = plan.filters.get("run_id") or plan.filters.get("workflow_run_id")
    if run_id:
        parsed_run_id = _uuid_filter_value(run_id)
        stmt = stmt.where(
            WorkflowNodeExecution.workflow_run_id == (parsed_run_id or uuid.UUID(int=0))
        )
    rows = list(
        ctx.db.execute(
            stmt.order_by(
                WorkflowNodeExecution.created_at.desc(), WorkflowNodeExecution.id.desc()
            ).limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(node.id),
            "workflow_run_id": str(node.workflow_run_id),
            "node_id": node.node_id,
            "node_type": node.node_type,
            "status": node.status,
            "retry_count": node.retry_count,
            "error": node.error,
            "produced_artifact_ids": _json_loads(node.produced_artifact_ids_json, []),
            "started_at": _iso(node.started_at),
            "finished_at": _iso(node.finished_at),
        }
        for node in rows
    ]
    return _section(
        resource_key=resource_key,
        label="Run Node Executions",
        status=_status_for_records(records),
        resolver="run_nodes",
        columns=["node_id", "node_type", "status", "retry_count", "error"],
        records=records,
        links=[{"label": "Runs", "href": "/runs"}],
        filters=plan.filters,
    )


def _resolve_agent_traces(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    stmt = select(AgentExecutionTrace).where(AgentExecutionTrace.workspace_id == ctx.workspace.id)
    run_id = plan.filters.get("run_id") or plan.filters.get("workflow_run_id")
    if run_id:
        parsed_run_id = _uuid_filter_value(run_id)
        stmt = stmt.where(
            AgentExecutionTrace.workflow_run_id == (parsed_run_id or uuid.UUID(int=0))
        )
    node_id = plan.filters.get("node_id")
    if node_id:
        stmt = stmt.where(AgentExecutionTrace.node_id == str(node_id))
    status = plan.filters.get("status")
    if status:
        stmt = stmt.where(AgentExecutionTrace.status == str(status))
    rows = list(
        ctx.db.execute(
            stmt.order_by(
                AgentExecutionTrace.started_at.desc(), AgentExecutionTrace.id.desc()
            ).limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(trace.id),
            "workflow_run_id": str(trace.workflow_run_id),
            "workflow_node_execution_id": str(trace.workflow_node_execution_id),
            "node_id": trace.node_id,
            "node_type": trace.node_type,
            "attempt": trace.attempt,
            "executor_kind": trace.executor_kind,
            "status": trace.status,
            "duration_ms": trace.duration_ms,
            "input_summary": _json_loads(trace.input_summary_json, {}),
            "output_summary": _json_loads(trace.output_summary_json, {}),
            "tool_call_count": len(_json_loads(trace.tool_calls_json, [])),
            "artifact_ids": _json_loads(trace.artifact_ids_json, []),
            "token_usage": _json_loads(trace.token_usage_json, {}),
            "cost_summary": _json_loads(trace.cost_summary_json, {}),
            "evaluation_summary": _json_loads(trace.evaluation_summary_json, {}),
            "version_metadata": _json_loads(trace.version_metadata_json, {}),
            "error_summary": trace.error_summary,
            "started_at": _iso(trace.started_at),
            "finished_at": _iso(trace.finished_at),
        }
        for trace in rows
    ]
    return _section(
        resource_key=resource_key,
        label="Agent Execution Traces",
        status=_status_for_records(records),
        resolver="agent_traces",
        columns=[
            "node_id",
            "node_type",
            "attempt",
            "status",
            "duration_ms",
            "tool_call_count",
            "token_usage",
            "cost_summary",
            "started_at",
        ],
        records=records,
        links=[{"label": "Agents", "href": "/agents"}, {"label": "Runs", "href": "/runs"}],
        filters=plan.filters,
        redactions=["raw_inputs", "raw_outputs", "private_reasoning", "secrets"],
    )


def _resolve_run_signals(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    stmt = select(WorkflowSignalEvent).where(WorkflowSignalEvent.workspace_id == ctx.workspace.id)
    run_id = plan.filters.get("run_id") or plan.filters.get("workflow_run_id")
    if run_id:
        parsed_run_id = _uuid_filter_value(run_id)
        stmt = stmt.where(
            WorkflowSignalEvent.workflow_run_id == (parsed_run_id or uuid.UUID(int=0))
        )
    rows = list(
        ctx.db.execute(
            stmt.order_by(
                WorkflowSignalEvent.created_at.desc(), WorkflowSignalEvent.id.desc()
            ).limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(signal.id),
            "workflow_run_id": str(signal.workflow_run_id),
            "signal_type": signal.signal_type,
            "target_step": signal.target_step,
            "note": signal.note,
            "created_by_user_id": str(signal.created_by_user_id)
            if signal.created_by_user_id
            else None,
            "created_at": _iso(signal.created_at),
        }
        for signal in rows
    ]
    return _section(
        resource_key=resource_key,
        label="Run Signals",
        status=_status_for_records(records),
        resolver="run_signals",
        columns=["signal_type", "target_step", "note", "created_at"],
        records=records,
        links=[{"label": "Monitor", "href": "/monitor"}],
        filters=plan.filters,
    )


def _resolve_artifacts(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(Artifact)
            .where(Artifact.workspace_id == ctx.workspace.id)
            .order_by(Artifact.created_at.desc(), Artifact.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = []
    relationships: list[PlatformRelationship] = []
    for artifact in rows:
        artifact_id = str(artifact.id)
        parent_ids = [
            str(parent_id) for parent_id in _json_loads(artifact.parent_artifact_ids_json, [])
        ]
        records.append(
            {
                "id": artifact_id,
                "kind": artifact.kind,
                "workflow_run_id": str(artifact.workflow_run_id)
                if artifact.workflow_run_id
                else None,
                "produced_by_node_id": artifact.produced_by_node_id,
                "parent_artifact_ids": parent_ids,
                "uri_scheme": urlparse(artifact.uri).scheme or "local",
                "created_at": _iso(artifact.created_at),
            }
        )
        artifact_ref = PlatformEntityRef(
            resource_key="artifacts",
            entity_id=artifact_id,
            label=f"{artifact.kind}:{artifact_id[:8]}",
            href="/reports",
        )
        if artifact.workflow_run_id:
            relationships.append(
                PlatformRelationship(
                    source=PlatformEntityRef(
                        resource_key="runs",
                        entity_id=str(artifact.workflow_run_id),
                        label=f"run:{str(artifact.workflow_run_id)[:8]}",
                        href="/runs",
                    ),
                    target=artifact_ref,
                    relationship_type="produced",
                )
            )
        for parent_id in parent_ids:
            relationships.append(
                PlatformRelationship(
                    source=PlatformEntityRef(
                        resource_key="artifacts",
                        entity_id=parent_id,
                        label=f"artifact:{parent_id[:8]}",
                        href="/reports",
                    ),
                    target=artifact_ref,
                    relationship_type="parent_of",
                )
            )
    return _section(
        resource_key=resource_key,
        label="Artifacts",
        status=_status_for_records(records),
        resolver="artifacts",
        columns=["kind", "workflow_run_id", "produced_by_node_id", "uri_scheme", "created_at"],
        records=records,
        relationships=relationships,
        links=[{"label": "Reports", "href": "/reports"}],
        redactions=["uri.external_credentials"],
        filters=plan.filters,
    )


def _resolve_approvals(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(HitlApproval)
            .where(HitlApproval.workspace_id == ctx.workspace.id)
            .order_by(HitlApproval.created_at.desc(), HitlApproval.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(item.id),
            "workflow_run_id": str(item.workflow_run_id) if item.workflow_run_id else None,
            "step_key": item.step_key,
            "status": str(item.status.value if hasattr(item.status, "value") else item.status),
            "expires_at": _iso(item.expires_at),
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }
        for item in rows
    ]
    return _section(
        resource_key=resource_key,
        label="HITL Approvals",
        status=_status_for_records(records),
        resolver="approvals",
        columns=["step_key", "status", "workflow_run_id", "expires_at", "created_at"],
        records=records,
        filters=plan.filters,
    )


def _resolve_audit(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    rows = list(
        ctx.db.execute(
            select(AuditLog)
            .where(AuditLog.workspace_id == ctx.workspace.id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(plan.limit)
        ).scalars()
    )
    records = [
        {
            "id": str(item.id),
            "actor_user_id": str(item.actor_user_id) if item.actor_user_id else None,
            "action": item.action,
            "details": item.details,
            "created_at": _iso(item.created_at),
        }
        for item in rows
    ]
    return _section(
        resource_key=resource_key,
        label="Audit Log",
        status=_status_for_records(records),
        resolver="audit",
        columns=["actor_user_id", "action", "details", "created_at"],
        records=records,
        links=[{"label": "Admin", "href": "/admin"}],
        filters=plan.filters,
    )


def _resolve_admin_ops(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    jobs = list(
        ctx.db.execute(
            select(ScheduledJob)
            .order_by(ScheduledJob.next_run_at.asc(), ScheduledJob.job_name)
            .limit(plan.limit)
        ).scalars()
    )
    metrics = {
        "dlq": ctx.db.execute(
            select(func.count())
            .select_from(OutboxDlq)
            .where(OutboxDlq.tenant_id == ctx.workspace.tenant_id)
        ).scalar()
        or 0,
        "scheduled_jobs": len(jobs),
        "enabled_scheduled_jobs": sum(1 for job in jobs if job.enabled),
    }
    records = [
        {
            "job_name": job.job_name,
            "job_type": job.job_type,
            "enabled": job.enabled,
            "cron_expression": job.cron_expression,
            "interval_seconds": job.interval_seconds,
            "last_run_status": job.last_run_status,
            "last_run_at": _iso(job.last_run_at),
            "next_run_at": _iso(job.next_run_at),
            "leader_id": job.leader_id,
        }
        for job in jobs
    ]
    return _section(
        resource_key=resource_key,
        label="Admin Operations",
        status="ok",
        resolver="admin_ops",
        metrics=metrics,
        records=records or [metrics],
        columns=["job_name", "job_type", "enabled", "last_run_status", "next_run_at", "leader_id"],
        links=[{"label": "Admin", "href": "/admin"}],
        filters=plan.filters,
    )


def _resolve_finops(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    artifact_count = (
        ctx.db.execute(
            select(func.count())
            .select_from(Artifact)
            .where(Artifact.tenant_id == ctx.workspace.tenant_id)
        ).scalar()
        or 0
    )
    upload_count = (
        ctx.db.execute(
            select(func.count())
            .select_from(ChatUpload)
            .where(ChatUpload.tenant_id == ctx.workspace.tenant_id)
        ).scalar()
        or 0
    )
    run_count = (
        ctx.db.execute(
            select(func.count())
            .select_from(WorkflowRun)
            .where(WorkflowRun.tenant_id == ctx.workspace.tenant_id)
        ).scalar()
        or 0
    )
    now = datetime.now(UTC)
    expired_count = (
        ctx.db.execute(
            select(func.count())
            .select_from(Artifact)
            .where(Artifact.tenant_id == ctx.workspace.tenant_id)
            .where(Artifact.expires_at.is_not(None))
            .where(Artifact.expires_at < now)
        ).scalar()
        or 0
    )
    traces = list(
        ctx.db.execute(
            select(AgentExecutionTrace.cost_summary_json, AgentExecutionTrace.token_usage_json)
            .where(AgentExecutionTrace.tenant_id == ctx.workspace.tenant_id)
            .limit(5000)
        ).all()
    )
    trace_cost_usd = 0.0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    cost_records = 0
    token_records = 0
    for cost_raw, token_raw in traces:
        cost = _json_loads(cost_raw, {})
        if isinstance(cost, dict):
            amount = _first_numeric(cost, ["usd", "total_usd", "cost_usd", "amount_usd"])
            if amount is not None:
                trace_cost_usd += amount
                cost_records += 1
        usage = _json_loads(token_raw, {})
        if isinstance(usage, dict):
            token_records += 1
            prompt_tokens += int(_first_numeric(usage, ["prompt_tokens", "input_tokens"]) or 0)
            completion_tokens += int(
                _first_numeric(usage, ["completion_tokens", "output_tokens"]) or 0
            )
            total_tokens += int(_first_numeric(usage, ["total_tokens"]) or 0)
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    recommendations = _finops_recommendations(int(artifact_count), int(expired_count))
    record = {
        "artifacts": int(artifact_count),
        "uploads": int(upload_count),
        "expired_artifacts": int(expired_count),
        "workflow_runs": int(run_count),
        "agent_trace_cost_usd": round(trace_cost_usd, 6),
        "agent_trace_cost_records": cost_records,
        "agent_trace_token_records": token_records,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "billing_grade": "trace_reported_estimate",
        "artifact_retention_days": settings.artifact_retention_days,
        "chat_upload_max_mb": settings.chat_upload_max_mb,
        "agent_cache_enabled": settings.agent_cache_enabled,
        "recommendations": recommendations,
    }
    return _section(
        resource_key=resource_key,
        label="FinOps and Cost Summary",
        status="ok",
        resolver="finops",
        metrics={
            key: value for key, value in record.items() if isinstance(value, (int, float, bool))
        },
        records=[record],
        columns=list(record.keys()),
        links=[{"label": "Admin", "href": "/admin"}],
        filters=plan.filters,
    )


def _resolve_modelops_artifacts(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    summary = get_modelops_summary(ctx.db, workspace_id=ctx.workspace.id)
    records = summary["registry"][: plan.limit]
    monitor_records = summary["monitors"][: plan.limit]
    retrain_records = summary["retrain_candidates"][: plan.limit]
    metrics = summary["metrics"]
    return _section(
        resource_key=resource_key,
        label="ModelOps State",
        status=_status_for_records(records + monitor_records + retrain_records),
        resolver="modelops_artifacts",
        message="ModelOps summary uses the persisted registry, monitor, and deployment store when available, with artifact-backed candidates as fallback evidence.",
        columns=[
            "model_id",
            "version",
            "stage",
            "workflow_run_id",
            "monitoring_status",
            "drift_status",
            "performance_status",
            "retrain_candidate",
            "created_at",
        ],
        records=records,
        metrics={
            **metrics,
            "monitor_records": len(monitor_records),
            "retrain_records": len(retrain_records),
        },
        links=[
            {"label": "ModelOps", "href": "/modelops"},
            {"label": "Reports", "href": "/reports"},
        ],
        redactions=["uri.external_credentials"],
        filters=plan.filters,
        relationships=[
            PlatformRelationship(
                source=PlatformEntityRef(
                    resource_key="modelops",
                    entity_id=item["model_id"],
                    label=item["version"],
                    href="/modelops",
                ),
                target=PlatformEntityRef(
                    resource_key="artifacts",
                    entity_id=artifact_id,
                    label=f"artifact:{artifact_id[:8]}",
                    href="/reports",
                ),
                relationship_type="uses_monitor",
            )
            for item in retrain_records
            for artifact_id in item.get("linked_monitor_ids", [])
        ],
    )


def _resolve_control_plane_adapters(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    records = [
        {
            "adapter": "product_chat",
            "audience": "workspace users",
            "dependency_direction": "chat -> control_plane",
            "status": "active_internal",
            "notes": "Chat routes platform questions through catalog, policy, resolver, and provenance contracts.",
        },
        {
            "adapter": "cli",
            "audience": "developers and operators",
            "dependency_direction": "cli -> control_plane_api",
            "status": "available_local",
            "notes": "tools/platform_control_plane_cli.py calls catalog, query, actions/plan, and actions/execute.",
        },
        {
            "adapter": "mcp",
            "audience": "external integrations",
            "dependency_direction": "mcp -> control_plane_api",
            "status": "available_local_stdio_adapter",
            "notes": "tools/platform_control_plane_mcp_adapter.py exposes the same API over a dependency-light stdio bridge.",
        },
    ]
    return _section(
        resource_key=resource_key,
        label="Control Plane Adapters",
        status="ok",
        resolver="control_plane_adapters",
        columns=["adapter", "audience", "dependency_direction", "status", "notes"],
        records=records[: plan.limit],
        metrics={
            "active_internal": sum(1 for item in records if item["status"] == "active_internal"),
            "planned": sum(1 for item in records if item["status"] == "planned"),
        },
        links=[
            {"label": "AI Workspace", "href": "/ai-workspace"},
            {"label": "Control Plane Docs", "href": "/docs/universal-platform-control-plane.md"},
        ],
        filters=plan.filters,
    )


def _resolve_release_docs(
    ctx: ControlPlaneContext, plan: PlatformQueryPlan, resource_key: str
) -> PlatformQuerySection:
    root = Path(__file__).resolve().parents[4]
    doc_paths = [
        "README.md",
        "FORME.md",
        "specification.md",
        "implementation.md",
        "tasks.md",
        "docs/RELEASE.md",
        "docs/release-readiness-checklist.md",
        "docs/launch-checklist.md",
        "docs/task-status-review-2026-06-03.md",
        "docs/API.md",
        "docs/route-api-contract-summary.md",
        "docs/route-authorization-matrix.md",
        "docs/MAINTAINABILITY.md",
        "docs/dead-code-dynamic-surface-triage.md",
        "docs/release-profile-fallback-review.md",
        "docs/release-dependency-lock-policy.md",
        "docs/STRATEGY.md",
        "docs/product-strategy-agentic-dsml-platform.md",
        "docs/RELEASE-NOTES.md",
        "docs/release-notes-template.md",
        "docs/universal-platform-control-plane.md",
        "docs/M22-RUNTIME.md",
        "docs/m22-lifecycle-parity-matrix.md",
        "apps/platform-api-app/docs/m22_orchestration_status.md",
        "frontend/RUNBOOK.md",
        "frontend/README.md",
        "frontend/docs/runbook-frontend.md",
        "security-report/verified-findings.md",
    ]
    records: list[dict[str, Any]] = []
    raw_terms = str(plan.filters.get("search") or plan.query or "")
    terms = [
        token
        for token in re.findall(r"[A-Za-z0-9_.-]{3,}", raw_terms.lower())
        if token
        not in {"docs", "document", "release", "status", "task", "tasks", "query", "platform"}
    ][:8]
    for relative in doc_paths:
        path = root / relative
        exists = path.exists()
        title = None
        summary = None
        matches: list[dict[str, Any]] = []
        if exists:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                non_empty = [line.strip() for line in lines if line.strip()]
                title = next(
                    (line.lstrip("# ").strip() for line in non_empty if line.startswith("#")),
                    relative,
                )
                summary = next((line for line in non_empty if not line.startswith("#")), None)
                open_tasks = sum(1 for line in lines if "- [ ]" in line)
                closed_tasks = sum(1 for line in lines if "- [x]" in line.lower())
                if terms:
                    for line_no, line in enumerate(lines, start=1):
                        lowered = line.lower()
                        if any(term in lowered for term in terms):
                            matches.append({"line": line_no, "snippet": line.strip()[:240]})
                            if len(matches) >= 5:
                                break
            except OSError:
                summary = "Could not read document."
                open_tasks = 0
                closed_tasks = 0
        else:
            open_tasks = 0
            closed_tasks = 0
        records.append(
            {
                "path": relative,
                "exists": exists,
                "title": title or relative,
                "summary": summary,
                "matches": matches,
                "match_count": len(matches),
                "open_tasks": open_tasks,
                "closed_tasks": closed_tasks,
                "updated_at": _iso(datetime.fromtimestamp(path.stat().st_mtime, tz=UTC))
                if exists
                else None,
            }
        )
    return _section(
        resource_key=resource_key,
        label="Release and Product Docs",
        status=_status_for_records(records),
        resolver="release_docs",
        columns=[
            "path",
            "exists",
            "title",
            "match_count",
            "open_tasks",
            "closed_tasks",
            "updated_at",
        ],
        records=records,
        metrics={
            "documents": len(records),
            "existing_documents": sum(1 for record in records if record["exists"]),
            "matching_documents": sum(1 for record in records if record["match_count"]),
            "open_tasks": sum(int(record["open_tasks"]) for record in records),
            "closed_tasks": sum(int(record["closed_tasks"]) for record in records),
        },
        filters=plan.filters,
    )


RESOLVERS: dict[str, Resolver] = {
    "overview": _resolve_overview,
    "identity": _resolve_identity,
    "configuration": _resolve_configuration,
    "data_sources": _resolve_data_sources,
    "chat_uploads": _resolve_chat_uploads,
    "workflows": _resolve_workflows,
    "workflow_schedules": _resolve_workflow_schedules,
    "runs": _resolve_runs,
    "run_nodes": _resolve_run_nodes,
    "agent_traces": _resolve_agent_traces,
    "run_signals": _resolve_run_signals,
    "artifacts": _resolve_artifacts,
    "approvals": _resolve_approvals,
    "audit": _resolve_audit,
    "admin_ops": _resolve_admin_ops,
    "finops": _resolve_finops,
    "modelops_artifacts": _resolve_modelops_artifacts,
    "control_plane_adapters": _resolve_control_plane_adapters,
    "release_docs": _resolve_release_docs,
}


def _first_schedule_trigger(triggers: Any) -> dict[str, Any] | None:
    if not isinstance(triggers, list):
        return None
    for trigger in triggers:
        if isinstance(trigger, dict) and trigger.get("type") in {"schedule", "cron"}:
            return trigger
    return None


def _finops_recommendations(artifact_count: int, expired_count: int) -> list[str]:
    recs: list[str] = []
    if expired_count > 0:
        recs.append(f"Run artifact cleanup for {expired_count} expired artifact(s).")
    if artifact_count > 10_000:
        recs.append("Review artifact_retention_days to control storage growth.")
    if settings.agent_cache_enabled and not settings.agent_cache_redis_url:
        recs.append("Configure Redis for distributed agent cache before release-like scale.")
    if not recs:
        recs.append("FinOps configuration looks stable for current local evidence.")
    return recs


def _uuid_filter_value(raw: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw))
    except (TypeError, ValueError, AttributeError):
        return None


def chat_platform_reply(
    ctx: ControlPlaneContext,
    prompt: str,
    *,
    action_plan: PlatformActionPlan | None = None,
) -> tuple[str, list[dict[str, Any]]] | None:
    plan = plan_query_from_text(prompt)
    if not plan.resource_keys and action_plan is None:
        return None
    result = execute_platform_query(ctx, plan)
    result = attach_action_plan(result, action_plan)
    payload = result.model_dump(mode="json")
    return result.summary, [payload]


def build_context_for_chat_session(db, session: ChatSession) -> ControlPlaneContext | None:
    membership = db.execute(
        select(WorkspaceMembership)
        .where(WorkspaceMembership.workspace_id == session.workspace_id)
        .where(WorkspaceMembership.user_id == session.user_id)
    ).scalar_one_or_none()
    if membership is None:
        return None
    user = db.get(User, session.user_id)
    workspace = db.get(Workspace, session.workspace_id)
    if user is None or workspace is None:
        return None
    return ControlPlaneContext(db=db, user=user, workspace=workspace, membership=membership)
