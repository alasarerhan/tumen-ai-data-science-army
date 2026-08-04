from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from platform_api.control_plane.catalog import get_descriptor
from platform_api.control_plane.policies import ControlPlaneContext, policy_engine
from platform_api.control_plane.schemas import PlatformActionPlan, PlatformActionResult
from platform_api.core.service_errors import ConflictError, ValidationError
from platform_api.db.models import WorkflowSignalEvent
from platform_api.services.audit_service import write_audit_log
from platform_api.services.run_orchestration_service import create_orchestration_run_id
from platform_api.services.run_service import (
    create_workflow_run_record,
    get_run_by_id_for_workspace,
    get_run_by_id_for_workspace_for_update,
    get_workflow_spec_for_run,
)
from platform_api.services.workflow_node_execution_service import (
    create_node_executions_for_run,
    resume_run_from_failed_node,
    retry_node_execution,
)
from platform_api.services.workflow_queue_service import enqueue_workflow_run
from platform_api.services.workflow_service import (
    archive_workflow_spec,
    build_workflow_validation_summary,
    get_workflow_spec_for_workspace,
    publish_workflow_spec,
)

ALLOWED_SIGNAL_TYPES = {
    "pause",
    "resume",
    "skip",
    "modify",
    "annotate",
    "cancel",
    "node_started",
    "node_progress",
    "node_succeeded",
    "node_failed",
    "artifact_created",
    "approval_required",
    "run_completed",
}


@dataclass(frozen=True)
class _ActionDefinition:
    action_name: str
    resource_key: str
    required_role: str
    risk_level: str
    confirmation_required: bool
    required_arguments: tuple[str, ...]
    summary_template: str


ACTION_DEFINITIONS: dict[str, _ActionDefinition] = {
    "workflows.publish": _ActionDefinition(
        "workflows.publish",
        "workflows",
        "workspace_admin",
        "medium",
        True,
        ("workflow_id",),
        "Publish workflow {workflow_id}.",
    ),
    "workflows.archive": _ActionDefinition(
        "workflows.archive",
        "workflows",
        "workspace_admin",
        "medium",
        True,
        ("workflow_id",),
        "Archive workflow {workflow_id}.",
    ),
    "workflows.trigger": _ActionDefinition(
        "workflows.trigger",
        "workflows",
        "member",
        "medium",
        True,
        ("workflow_id",),
        "Trigger workflow {workflow_id}.",
    ),
    "runs.cancel": _ActionDefinition(
        "runs.cancel",
        "runs",
        "member",
        "medium",
        True,
        ("run_id",),
        "Cancel run {run_id}.",
    ),
    "runs.retry": _ActionDefinition(
        "runs.retry",
        "runs",
        "member",
        "medium",
        True,
        ("run_id",),
        "Retry run {run_id}.",
    ),
    "runs.resume": _ActionDefinition(
        "runs.resume",
        "runs",
        "member",
        "medium",
        True,
        ("run_id",),
        "Resume failed nodes for run {run_id}.",
    ),
    "runs.nodes.retry": _ActionDefinition(
        "runs.nodes.retry",
        "run.nodes",
        "member",
        "medium",
        True,
        ("run_id", "node_id"),
        "Retry node {node_id} for run {run_id}.",
    ),
    "signals.emit": _ActionDefinition(
        "signals.emit",
        "run.signals",
        "member",
        "low",
        False,
        ("run_id", "signal_type"),
        "Emit {signal_type} signal for run {run_id}.",
    ),
    "schedules.pause": _ActionDefinition(
        "schedules.pause",
        "workflow.schedules",
        "workspace_admin",
        "medium",
        True,
        ("deployment_id",),
        "Pause schedule {deployment_id}.",
    ),
    "schedules.resume": _ActionDefinition(
        "schedules.resume",
        "workflow.schedules",
        "workspace_admin",
        "medium",
        True,
        ("deployment_id",),
        "Resume schedule {deployment_id}.",
    ),
    "dlq.replay": _ActionDefinition(
        "dlq.replay",
        "admin.ops",
        "tenant_admin",
        "high",
        True,
        ("event_id",),
        "Replay DLQ event {event_id}.",
    ),
}


def plan_action(
    ctx: ControlPlaneContext,
    *,
    action_name: str,
    arguments: dict[str, Any] | None = None,
) -> PlatformActionPlan:
    arguments = dict(arguments or {})
    definition = ACTION_DEFINITIONS.get(action_name)
    if definition is None:
        raise ValidationError("Unknown control-plane action")

    descriptor = get_descriptor(definition.resource_key)
    if descriptor is None:
        raise ValidationError("Action resource is not registered in the platform catalog")

    allowed = policy_engine.can_access_descriptor(ctx, descriptor)
    missing = [name for name in definition.required_arguments if not arguments.get(name)]
    denial_reason = None if allowed else f"{action_name} requires {definition.required_role} access"
    summary = _format_summary(definition.summary_template, arguments)
    return PlatformActionPlan(
        action_name=definition.action_name,
        resource_key=definition.resource_key,
        risk_level=definition.risk_level,  # type: ignore[arg-type]
        confirmation_required=definition.confirmation_required,
        allowed=allowed,
        summary=summary,
        arguments=arguments,
        missing_arguments=missing,
        denial_reason=denial_reason,
    )


async def execute_action(
    ctx: ControlPlaneContext,
    *,
    action_name: str,
    arguments: dict[str, Any] | None = None,
    confirmed: bool = False,
) -> PlatformActionResult:
    action_plan = plan_action(ctx, action_name=action_name, arguments=arguments)
    if not action_plan.allowed:
        return PlatformActionResult(
            status="denied",
            action_name=action_name,
            summary=action_plan.denial_reason or "Action denied.",
        )
    if action_plan.missing_arguments:
        return PlatformActionResult(
            status="missing_arguments",
            action_name=action_name,
            summary="Missing required action arguments.",
            data={"missing_arguments": action_plan.missing_arguments},
        )
    if action_plan.confirmation_required and not confirmed:
        return PlatformActionResult(
            status="planned",
            action_name=action_name,
            summary=action_plan.summary,
            data={
                "confirmation_required": True,
                "action_plan": action_plan.model_dump(mode="json"),
            },
        )

    data = await _execute_supported_action(ctx, action_plan)
    audit = write_audit_log(
        ctx.db,
        actor_user_id=ctx.user.id,
        action=f"control_plane.{action_name}",
        tenant_id=ctx.workspace.tenant_id,
        workspace_id=ctx.workspace.id,
        details=json.dumps(
            {"arguments": _safe_audit_arguments(action_plan.arguments), "result": data}, default=str
        ),
    )
    ctx.db.commit()
    return PlatformActionResult(
        status="executed",
        action_name=action_name,
        summary=f"Executed: {action_plan.summary}",
        data=data,
        audit_id=str(audit.id),
    )


def plan_action_from_text(query: str) -> PlatformActionPlan | None:
    normalized = query.lower()
    uuid_candidates = re.findall(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        query,
    )
    if not uuid_candidates:
        return None
    run_id = uuid_candidates[0]
    if any(word in normalized for word in ["cancel", "iptal"]):
        return PlatformActionPlan(
            action_name="runs.cancel",
            resource_key="runs",
            risk_level="medium",
            confirmation_required=True,
            allowed=True,
            summary=f"Cancel run {run_id}.",
            arguments={"run_id": run_id},
        )
    if any(word in normalized for word in ["retry", "rerun", "tekrar"]):
        return PlatformActionPlan(
            action_name="runs.retry",
            resource_key="runs",
            risk_level="medium",
            confirmation_required=True,
            allowed=True,
            summary=f"Retry run {run_id}.",
            arguments={"run_id": run_id},
        )
    return None


async def _execute_supported_action(
    ctx: ControlPlaneContext, action_plan: PlatformActionPlan
) -> dict[str, Any]:
    action_name = action_plan.action_name
    args = action_plan.arguments
    if action_name == "runs.cancel":
        return _cancel_run(ctx, str(args["run_id"]))
    if action_name == "runs.retry":
        return await _retry_run(ctx, str(args["run_id"]))
    if action_name == "runs.resume":
        return _resume_run(ctx, str(args["run_id"]))
    if action_name == "runs.nodes.retry":
        return _retry_node(ctx, str(args["run_id"]), str(args["node_id"]))
    if action_name == "workflows.publish":
        return _publish_workflow(ctx, str(args["workflow_id"]))
    if action_name == "workflows.archive":
        return _archive_workflow(ctx, str(args["workflow_id"]))
    if action_name == "workflows.trigger":
        return await _trigger_workflow(
            ctx, str(args["workflow_id"]), dict(args.get("parameters") or {})
        )
    if action_name == "signals.emit":
        return _emit_signal(
            ctx,
            str(args["run_id"]),
            signal_type=str(args["signal_type"]),
            target_step=args.get("target_step"),
            note=args.get("note"),
            payload=dict(args.get("payload") or {}),
        )
    if action_name in {"schedules.pause", "schedules.resume"}:
        return await _toggle_schedule(ctx, action_name, str(args["deployment_id"]))
    if action_name == "dlq.replay":
        return _replay_dlq(ctx, str(args["event_id"]))
    raise ValidationError("Unsupported control-plane action")


def _cancel_run(ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
    run = get_run_by_id_for_workspace_for_update(
        ctx.db, run_id=run_id, workspace_id=ctx.workspace.id
    )
    if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        raise ConflictError(f"Run is already in terminal state: {run.status}")
    run.status = "CANCELLED"
    run.updated_at = datetime.now(UTC)
    ctx.db.add(run)
    ctx.db.flush()
    return {"run_id": str(run.id), "status": run.status}


async def _retry_run(ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
    original = get_run_by_id_for_workspace(ctx.db, run_id=run_id, workspace_id=ctx.workspace.id)
    workflow_spec = None
    if original.workflow_spec_id:
        workflow_record = get_workflow_spec_for_run(
            ctx.db,
            workflow_spec_id=str(original.workflow_spec_id),
            workspace_id=ctx.workspace.id,
            workflow_version=original.workflow_version,
        )
        workflow_spec = json.loads(workflow_record.spec_json)
    effective_parameters = json.loads(original.parameters_json) if original.parameters_json else {}
    effective_parameters = {"requested_by": ctx.user.sub, **effective_parameters}
    flow_run_id = await create_orchestration_run_id(
        flow_key=original.flow_key,
        parameters=effective_parameters,
        workspace_id=str(ctx.workspace.id),
        user_id=str(ctx.user.id),
        tenant_id=str(ctx.workspace.tenant_id),
    )
    new_run = create_workflow_run_record(
        ctx.db,
        tenant_id=ctx.workspace.tenant_id,
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        flow_key=original.flow_key,
        prefect_flow_run_id=flow_run_id,
        parameters=effective_parameters,
        workflow_spec_id=original.workflow_spec_id,
        workflow_version=original.workflow_version,
        trigger_type=original.trigger_type,
        input_artifact_ids=json.loads(original.input_artifact_ids_json)
        if original.input_artifact_ids_json
        else [],
    )
    create_node_executions_for_run(ctx.db, run=new_run, workflow_spec=workflow_spec)
    return {"run_id": str(new_run.id), "prefect_flow_run_id": flow_run_id, "status": new_run.status}


def _resume_run(ctx: ControlPlaneContext, run_id: str) -> dict[str, Any]:
    run = get_run_by_id_for_workspace_for_update(
        ctx.db, run_id=run_id, workspace_id=ctx.workspace.id
    )
    nodes = resume_run_from_failed_node(ctx.db, run=run)
    queue_result = enqueue_workflow_run(
        run_id=run.id,
        workspace_id=ctx.workspace.id,
        tenant_id=ctx.workspace.tenant_id,
        workflow_spec_id=run.workflow_spec_id,
        trigger_type=run.trigger_type,
    )
    return {
        "run_id": str(run.id),
        "resumed_nodes": [node.node_id for node in nodes],
        "queue": queue_result,
    }


def _retry_node(ctx: ControlPlaneContext, run_id: str, node_id: str) -> dict[str, Any]:
    run = get_run_by_id_for_workspace_for_update(
        ctx.db, run_id=run_id, workspace_id=ctx.workspace.id
    )
    node = retry_node_execution(ctx.db, run=run, node_id=node_id)
    queue_result = enqueue_workflow_run(
        run_id=run.id,
        workspace_id=ctx.workspace.id,
        tenant_id=ctx.workspace.tenant_id,
        workflow_spec_id=run.workflow_spec_id,
        trigger_type=run.trigger_type,
    )
    return {
        "run_id": str(run.id),
        "node_id": node.node_id,
        "status": node.status,
        "queue": queue_result,
    }


def _publish_workflow(ctx: ControlPlaneContext, workflow_id: str) -> dict[str, Any]:
    record = publish_workflow_spec(
        ctx.db,
        workflow_id=workflow_id,
        workspace_id=str(ctx.workspace.id),
        user_id=ctx.user.id,
    )
    return {
        "workflow_id": str(record.id),
        "name": record.name,
        "version": record.version,
        "status": record.status,
    }


def _archive_workflow(ctx: ControlPlaneContext, workflow_id: str) -> dict[str, Any]:
    record = archive_workflow_spec(
        ctx.db,
        workflow_id=workflow_id,
        workspace_id=str(ctx.workspace.id),
        user_id=ctx.user.id,
    )
    return {
        "workflow_id": str(record.id),
        "name": record.name,
        "version": record.version,
        "status": record.status,
    }


async def _trigger_workflow(
    ctx: ControlPlaneContext, workflow_id: str, parameters: dict[str, Any]
) -> dict[str, Any]:
    record = get_workflow_spec_for_workspace(
        ctx.db,
        workflow_id=workflow_id,
        workspace_id=str(ctx.workspace.id),
        user_id=ctx.user.id,
    )
    spec = json.loads(record.spec_json)
    validation_summary = build_workflow_validation_summary(spec, workflow_name=record.name)
    if validation_summary["status"] == "invalid":
        raise ValidationError("Workflow contains invalid agent chains and cannot be triggered.")
    flow_run_id = await create_orchestration_run_id(
        flow_key=record.name,
        parameters=parameters,
        workspace_id=str(ctx.workspace.id),
        user_id=str(ctx.user.id),
        tenant_id=str(ctx.workspace.tenant_id),
    )
    run = create_workflow_run_record(
        ctx.db,
        tenant_id=ctx.workspace.tenant_id,
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        flow_key=record.name,
        prefect_flow_run_id=flow_run_id,
        parameters=parameters,
        workflow_spec_id=record.id,
        workflow_version=record.version,
        trigger_type="manual",
    )
    create_node_executions_for_run(ctx.db, run=run, workflow_spec=spec)
    queue_result = enqueue_workflow_run(
        run_id=run.id,
        workspace_id=ctx.workspace.id,
        tenant_id=ctx.workspace.tenant_id,
        workflow_spec_id=record.id,
        trigger_type="manual",
    )
    return {"run_id": str(run.id), "prefect_flow_run_id": flow_run_id, "queue": queue_result}


def _emit_signal(
    ctx: ControlPlaneContext,
    run_id: str,
    *,
    signal_type: str,
    target_step: str | None,
    note: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run = get_run_by_id_for_workspace(ctx.db, run_id=run_id, workspace_id=ctx.workspace.id)
    if signal_type not in ALLOWED_SIGNAL_TYPES:
        raise ValidationError(
            f"Unsupported signal_type. Allowed values: {', '.join(sorted(ALLOWED_SIGNAL_TYPES))}"
        )
    event = WorkflowSignalEvent(
        tenant_id=ctx.workspace.tenant_id,
        workspace_id=ctx.workspace.id,
        workflow_run_id=run.id,
        signal_type=signal_type,
        target_step=target_step,
        note=note,
        payload_json=json.dumps(payload or {}),
        created_by_user_id=ctx.user.id,
        created_at=datetime.now(UTC),
    )
    ctx.db.add(event)
    ctx.db.flush()
    return {"signal_id": str(event.id), "run_id": str(run.id), "signal_type": event.signal_type}


async def _toggle_schedule(
    ctx: ControlPlaneContext, action_name: str, deployment_id: str
) -> dict[str, Any]:
    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    scheduler = WorkflowSchedulerService(ctx.db)
    if action_name == "schedules.pause":
        return await scheduler.pause_scheduled_deployment(
            deployment_id,
            workspace_id=ctx.workspace.id,
            tenant_id=ctx.workspace.tenant_id,
        )
    return await scheduler.resume_scheduled_deployment(
        deployment_id,
        workspace_id=ctx.workspace.id,
        tenant_id=ctx.workspace.tenant_id,
    )


def _replay_dlq(ctx: ControlPlaneContext, event_id: str) -> dict[str, Any]:
    from platform_api.services.outbox import OutboxService

    outbox = OutboxService(ctx.db)
    event_uuid = uuid.UUID(event_id)
    new_event = outbox.replay_dlq_event(
        event_uuid,
        tenant_id=ctx.workspace.tenant_id,
        reviewed_by_user_id=ctx.user.id,
    )
    if new_event is None:
        return {"status": "not_found", "new_event_id": None}
    return {"status": "replayed", "new_event_id": str(new_event.id)}


def _format_summary(template: str, arguments: dict[str, Any]) -> str:
    try:
        return template.format(**{key: str(value) for key, value in arguments.items()})
    except KeyError:
        return template


def _safe_audit_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    safe = dict(arguments)
    for key in list(safe.keys()):
        if any(token in key.lower() for token in ["password", "secret", "token"]):
            safe[key] = "<redacted>"
    return safe
