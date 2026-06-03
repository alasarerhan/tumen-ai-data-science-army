"""Workflow scheduler service for Prefect deployment scheduling.

Implements scheduled workflow execution with:
* Prefect deployment integration
* Cron-based scheduling
* Leader election for distributed execution
* Automatic deployment creation/updates
* Distributed circuit breaker for multi-replica protection

Best Practices Reference:
https://docs-3.prefect.io/v3/how-to-guides/deployments/manage-schedules
https://docs-2.prefect.io/latest/concepts/schedules/

Usage
-----
::

    from platform_api.services.workflow_scheduler_service import WorkflowSchedulerService

    scheduler = WorkflowSchedulerService(db)

    # Create a scheduled deployment
    await scheduler.create_scheduled_deployment(
        workflow_spec=workflow_spec,
        cron="0 8 * * 1-5",  # Weekdays at 8am
    )

    # List scheduled deployments
    deployments = await scheduler.list_scheduled_deployments()
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from prometheus_client import Counter, Gauge
from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.core.config import settings
from platform_api.core.circuit_breaker import (
    CircuitBreakerConfig,
    DistributedCircuitBreaker,
)
from platform_api.db.models import WorkflowSpec

logger = logging.getLogger(__name__)


PREFECT_TIMEOUT_SECONDS = 30
PREFECT_CIRCUIT_BREAKER_THRESHOLD = 3
PREFECT_CIRCUIT_BREAKER_RESET_SECONDS = 60


PREFECT_CIRCUIT_BREAKER = DistributedCircuitBreaker(
    config=CircuitBreakerConfig(
        name="prefect",
        failure_threshold=PREFECT_CIRCUIT_BREAKER_THRESHOLD,
        reset_timeout_seconds=PREFECT_CIRCUIT_BREAKER_RESET_SECONDS,
    ),
    redis_url=settings.agent_cache_redis_url or None,
)


WORKFLOW_SCHEDULED_TOTAL = Counter(
    "platform_api_workflow_scheduled_total",
    "Total number of workflow schedules created",
    ["workflow_name"],
    registry=None,
)

WORKFLOW_TRIGGER_TOTAL = Counter(
    "platform_api_workflow_trigger_total",
    "Total number of scheduled workflow triggers",
    ["workflow_name", "status"],
    registry=None,
)

WORKFLOW_SCHEDULE_GAUGE = Gauge(
    "platform_api_workflow_schedules_active",
    "Number of active workflow schedules",
    registry=None,
)


class WorkflowSchedulerService:
    """Service for managing scheduled workflow deployments.

    Integrates with Prefect for reliable scheduled execution with
    leader election to prevent double execution in multi-replica deployments.

    Parameters
    ----------
    db : Session
        SQLAlchemy database session.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._prefect_available = self._check_prefect()

    def _check_prefect(self) -> bool:
        """Check if Prefect is available."""
        if importlib.util.find_spec("prefect") is None:
            logger.warning("Prefect not available, scheduled workflows will be disabled")
            return False
        return True

    async def create_scheduled_deployment(
        self,
        workflow_spec: WorkflowSpec,
        cron: Optional[str] = None,
        timezone: str = "UTC",
        parameters: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Create or update a Prefect deployment for scheduled execution.

        Parameters
        ----------
        workflow_spec : WorkflowSpec
            The workflow specification to schedule.
        cron : str | None
            Cron expression for scheduling (e.g., "0 8 * * 1-5").
        timezone : str
            Timezone for schedule (default: UTC).
        parameters : dict | None
            Default parameters for the workflow.
        enabled : bool
            Whether the schedule is enabled.

        Returns
        -------
        dict
            Deployment information including ID and schedule.
        """
        if not self._prefect_available:
            raise RuntimeError("Prefect is not available")

        if PREFECT_CIRCUIT_BREAKER.is_open():
            raise RuntimeError(
                "Prefect API is currently unavailable (circuit breaker open). "
                "Please try again later."
            )

        if not cron:
            logger.warning(
                "No cron expression provided for workflow %s, skipping schedule",
                workflow_spec.name,
            )
            return {"status": "skipped", "reason": "no_cron"}

        try:
            from prefect.client.orchestration import get_client

            spec_data = json.loads(workflow_spec.spec_json) if workflow_spec.spec_json else {}
            schedule_config = spec_data.get("schedule", {})
            effective_cron = cron or schedule_config.get("cron")
            effective_timezone = timezone or schedule_config.get("timezone", "UTC")

            if not effective_cron:
                raise ValueError("No cron expression provided")

            deployment_name = f"{workflow_spec.name}-v{workflow_spec.version}"

            async with get_client() as client:
                existing = await self._find_deployment_by_name(client, deployment_name)

                if existing:
                    deployment_id = existing["id"]
                    logger.info(
                        "Updating existing deployment: name=%s, id=%s, cron=%s",
                        deployment_name, deployment_id, effective_cron,
                    )
                else:
                    flow_name = f"workflow-{workflow_spec.name}"
                    deployment_id = await self._create_deployment(
                        client=client,
                        flow_name=flow_name,
                        deployment_name=deployment_name,
                        cron=effective_cron,
                        timezone=effective_timezone,
                        parameters={
                            "workflow_spec_id": str(workflow_spec.id),
                            "workspace_id": str(workflow_spec.workspace_id),
                            "tenant_id": str(workflow_spec.tenant_id),
                            **(parameters or {}),
                        },
                    )
                    logger.info(
                        "Created new deployment: name=%s, id=%s, cron=%s",
                        deployment_name, deployment_id, effective_cron,
                    )

            PREFECT_CIRCUIT_BREAKER.record_success()
            WORKFLOW_SCHEDULED_TOTAL.labels(workflow_name=workflow_spec.name).inc()
            WORKFLOW_SCHEDULE_GAUGE.inc()

            return {
                "deployment_id": deployment_id,
                "deployment_name": deployment_name,
                "cron": effective_cron,
                "timezone": effective_timezone,
                "enabled": enabled,
                "workflow_spec_id": str(workflow_spec.id),
            }

        except asyncio.TimeoutError:
            PREFECT_CIRCUIT_BREAKER.record_failure()
            logger.error(
                "Timeout creating deployment for workflow %s after %ds",
                workflow_spec.name, settings.prefect_api_timeout_seconds,
            )
            raise RuntimeError("Prefect API timeout. Please try again.")
        except Exception:
            PREFECT_CIRCUIT_BREAKER.record_failure()
            logger.error(
                "Failed to create scheduled deployment for workflow %s",
                workflow_spec.name,
            )
            raise RuntimeError("Failed to create scheduled deployment") from None

    async def _find_deployment_by_name(self, client, name: str) -> Optional[Dict]:
        """Find an existing deployment by name."""
        try:
            deployments = await asyncio.wait_for(
                client.read_deployments(),
                timeout=settings.prefect_api_timeout_seconds,
            )
            for dep in deployments:
                if dep.name == name:
                    return {"id": str(dep.id), "name": dep.name}
            return None
        except asyncio.TimeoutError:
            logger.error("Timeout finding deployment %s after %ds", name, settings.prefect_api_timeout_seconds)
            raise RuntimeError(f"Prefect API timeout while finding deployment {name}")
        except Exception as e:
            logger.error("Error finding deployment %s: %s", name, e)
            raise

    async def _create_deployment(
        self,
        client,
        flow_name: str,
        deployment_name: str,
        cron: str,
        timezone: str,
        parameters: Dict[str, Any],
    ) -> str:
        """Create a new Prefect deployment with schedule."""
        try:
            from prefect.schedules import CronSchedule

            schedule = CronSchedule(cron=cron, timezone=timezone)

            deployment = await asyncio.wait_for(
                client.create_deployment(
                    name=deployment_name,
                    flow_name=flow_name,
                    schedule=schedule,
                    parameters=parameters,
                    work_pool_name=settings.prefect_work_pool_name or None,
                    work_queue_name=settings.prefect_work_queue_name or None,
                ),
                timeout=settings.prefect_api_timeout_seconds,
            )

            return str(deployment.id)

        except asyncio.TimeoutError:
            logger.error("Timeout creating deployment %s after %ds", deployment_name, settings.prefect_api_timeout_seconds)
            raise RuntimeError(f"Prefect API timeout while creating deployment {deployment_name}")
        except Exception as e:
            logger.error("Failed to create deployment: %s", e)
            raise

    async def list_scheduled_deployments(
        self,
        *,
        workspace_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
    ) -> List[Dict[str, Any]]:
        """List all scheduled workflow deployments.

        Returns
        -------
        list[dict]
            List of deployment information.
        """
        if not self._prefect_available:
            return []

        if PREFECT_CIRCUIT_BREAKER.is_open():
            logger.warning("Prefect circuit breaker open, returning empty list")
            return []

        try:
            from prefect.client.orchestration import get_client

            async with get_client() as client:
                deployments = await asyncio.wait_for(
                    client.read_deployments(),
                    timeout=settings.prefect_api_timeout_seconds,
                )

                result = []
                for dep in deployments:
                    dep_parameters = dep.parameters or {}
                    if workspace_id is not None and str(dep_parameters.get("workspace_id")) != str(workspace_id):
                        continue
                    if tenant_id is not None and str(dep_parameters.get("tenant_id")) != str(tenant_id):
                        continue
                    schedule_info = None
                    if dep.schedule:
                        schedule_info = {
                            "type": type(dep.schedule).__name__,
                            "cron": getattr(dep.schedule, "cron", None),
                            "timezone": getattr(dep.schedule, "timezone", None),
                        }

                    result.append({
                        "id": str(dep.id),
                        "name": dep.name,
                        "flow_name": dep.flow_name,
                        "schedule": schedule_info,
                        "parameters": dep_parameters,
                        "created": dep.created.isoformat() if dep.created else None,
                        "updated": dep.updated.isoformat() if dep.updated else None,
                    })

                PREFECT_CIRCUIT_BREAKER.record_success()
                return result

        except asyncio.TimeoutError:
            PREFECT_CIRCUIT_BREAKER.record_failure()
            logger.error("Timeout listing deployments after %ds", settings.prefect_api_timeout_seconds)
            return []
        except Exception:
            PREFECT_CIRCUIT_BREAKER.record_failure()
            logger.error("Failed to list deployments")
            return []

    async def trigger_scheduled_workflow(
        self,
        workflow_spec_id: uuid.UUID,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Manually trigger a scheduled workflow.

        Parameters
        ----------
        workflow_spec_id : uuid.UUID
            ID of the workflow spec to trigger.
        parameters : dict | None
            Additional parameters for this run.

        Returns
        -------
        dict
            Flow run information.
        """
        workflow_spec = self._db.execute(
            select(WorkflowSpec).where(WorkflowSpec.id == workflow_spec_id)
        ).scalar_one_or_none()

        if not workflow_spec:
            raise ValueError(f"Workflow spec not found: {workflow_spec_id}")

        try:
            from platform_api.services.run_orchestration_service import create_orchestration_run_id

            flow_run_id = await create_orchestration_run_id(
                flow_key=workflow_spec.name,
                parameters={
                    "workflow_spec_id": str(workflow_spec_id),
                    "workspace_id": str(workflow_spec.workspace_id),
                    "triggered_at": datetime.now(UTC).isoformat(),
                    **(parameters or {}),
                },
            )

            WORKFLOW_TRIGGER_TOTAL.labels(
                workflow_name=workflow_spec.name, status="success"
            ).inc()

            return {
                "flow_run_id": flow_run_id,
                "workflow_spec_id": str(workflow_spec_id),
                "status": "triggered",
            }

        except Exception as e:
            WORKFLOW_TRIGGER_TOTAL.labels(
                workflow_name=workflow_spec.name, status="failed"
            ).inc()
            logger.error("Failed to trigger workflow %s: %s", workflow_spec.name, e)
            raise

    async def pause_scheduled_deployment(
        self,
        deployment_id: str,
        *,
        workspace_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str | None = None,
    ) -> Dict[str, Any]:
        """Pause a scheduled deployment.

        Parameters
        ----------
        deployment_id : str
            ID of the deployment to pause.

        Returns
        -------
        dict
            Updated deployment status.
        """
        if not self._prefect_available:
            raise RuntimeError("Prefect is not available")

        try:
            deployment = await self._get_workspace_deployment(
                deployment_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
            )
            if deployment is None:
                raise ValueError(f"Deployment not found for workspace: {deployment_id}")

            from prefect.client.orchestration import get_client

            async with get_client() as client:
                await asyncio.wait_for(
                    client.set_deployment_paused_state(
                        deployment_id=uuid.UUID(deployment_id),
                        paused=True,
                    ),
                    timeout=settings.prefect_api_timeout_seconds,
                )

            WORKFLOW_SCHEDULE_GAUGE.dec()

            return {
                "deployment_id": deployment_id,
                "status": "paused",
            }

        except asyncio.TimeoutError:
            logger.error("Timeout pausing deployment %s after %ds", deployment_id, settings.prefect_api_timeout_seconds)
            raise RuntimeError(f"Prefect API timeout while pausing deployment {deployment_id}")
        except Exception as e:
            logger.error("Failed to pause deployment %s: %s", deployment_id, e)
            raise

    async def resume_scheduled_deployment(
        self,
        deployment_id: str,
        *,
        workspace_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str | None = None,
    ) -> Dict[str, Any]:
        """Resume a paused scheduled deployment.

        Parameters
        ----------
        deployment_id : str
            ID of the deployment to resume.

        Returns
        -------
        dict
            Updated deployment status.
        """
        if not self._prefect_available:
            raise RuntimeError("Prefect is not available")

        try:
            deployment = await self._get_workspace_deployment(
                deployment_id,
                workspace_id=workspace_id,
                tenant_id=tenant_id,
            )
            if deployment is None:
                raise ValueError(f"Deployment not found for workspace: {deployment_id}")

            from prefect.client.orchestration import get_client

            async with get_client() as client:
                await asyncio.wait_for(
                    client.set_deployment_paused_state(
                        deployment_id=uuid.UUID(deployment_id),
                        paused=False,
                    ),
                    timeout=settings.prefect_api_timeout_seconds,
                )

            WORKFLOW_SCHEDULE_GAUGE.inc()

            return {
                "deployment_id": deployment_id,
                "status": "resumed",
            }

        except asyncio.TimeoutError:
            logger.error("Timeout resuming deployment %s after %ds", deployment_id, settings.prefect_api_timeout_seconds)
            raise RuntimeError(f"Prefect API timeout while resuming deployment {deployment_id}")
        except Exception as e:
            logger.error("Failed to resume deployment %s: %s", deployment_id, e)
            raise

    async def delete_scheduled_deployments(
        self,
        *,
        tenant_id: uuid.UUID | str,
        workspace_id: uuid.UUID | str | None = None,
    ) -> Dict[str, Any]:
        """Delete scheduled deployments owned by a tenant or workspace."""
        if not self._prefect_available:
            logger.info("Prefect unavailable; skipping scheduled deployment cleanup")
            return {"deleted": 0, "errors": []}

        deployments = await self.list_scheduled_deployments(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
        )
        if not deployments:
            return {"deleted": 0, "errors": []}

        errors: list[str] = []
        deleted = 0

        try:
            from prefect.client.orchestration import get_client

            async with get_client() as client:
                delete_method = getattr(client, "delete_deployment", None)
                if delete_method is None:
                    raise RuntimeError("Prefect client does not support delete_deployment")

                for deployment in deployments:
                    deployment_id = deployment["id"]
                    try:
                        await asyncio.wait_for(
                            delete_method(uuid.UUID(deployment_id)),
                            timeout=settings.prefect_api_timeout_seconds,
                        )
                        deleted += 1
                    except asyncio.TimeoutError:
                        errors.append(f"{deployment_id}: timeout")
                    except Exception as exc:
                        errors.append(f"{deployment_id}: {exc}")
        except Exception as exc:
            logger.error("Failed to delete scheduled deployments: %s", exc)
            errors.append(str(exc))

        return {"deleted": deleted, "errors": errors}

    async def _get_workspace_deployment(
        self,
        deployment_id: str,
        *,
        workspace_id: uuid.UUID | str,
        tenant_id: uuid.UUID | str | None = None,
    ) -> Optional[Dict[str, Any]]:
        deployments = await self.list_scheduled_deployments(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
        )
        for deployment in deployments:
            if deployment["id"] == deployment_id:
                return deployment
        return None


__all__ = [
    "WorkflowSchedulerService",
    "WORKFLOW_SCHEDULED_TOTAL",
    "WORKFLOW_TRIGGER_TOTAL",
    "WORKFLOW_SCHEDULE_GAUGE",
]
