"""Workflow version manager with canary deployment support.

This module manages workflow versions and canary deployments,
including staged rollouts and automated rollbacks.

Best Practices Reference:
https://zylos.ai/research/2026-03-06-ai-agent-version-management-safe-upgrade-patterns
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from redis import Redis
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from platform_api.versioning.models import (
    CanaryDeployment,
    DEFAULT_ROLLBACK_TRIGGERS,
    DEFAULT_STAGES,
    WorkflowVersion,
)

logger = logging.getLogger(__name__)


class WorkflowVersionManager:
    """Manage workflow versions with canary deployment support.
    
    This class handles:
    - Creating and publishing workflow versions
    - Canary deployments with staged rollout
    - Automated rollback based on metrics
    - Version history tracking
    
    Example
    -------
    >>> manager = WorkflowVersionManager(db, redis)
    >>> version_id = await manager.create_version(
    ...     workflow_id="wf-123",
    ...     workflow_spec={"name": "My Workflow", "steps": [...]},
    ...     changelog="Added new step",
    ... )
    >>> await manager.deploy_version(version_id, strategy="canary")
    """
    
    def __init__(self, db: Session, redis: Optional[Redis] = None):
        self.db = db
        self.redis = redis

    def _lock_workflow_versions(self, workflow_id: str) -> None:
        bind = getattr(self.db, "get_bind", lambda: None)()
        if bind is None or bind.dialect.name != "postgresql":
            return
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:workflow_key))"),
            {"workflow_key": workflow_id},
        )
    
    async def create_version(
        self,
        workflow_id: str,
        workflow_spec: Dict[str, Any],
        changelog: str = "",
        created_by: Optional[str] = None,
    ) -> str:
        """Create a new version of a workflow.
        
        Parameters
        ----------
        workflow_id : str
            ID of the workflow.
        workflow_spec : Dict[str, Any]
            The workflow specification.
        changelog : str
            Description of changes.
        created_by : Optional[str]
            User ID who created this version.
        
        Returns
        -------
        str
            The new version ID.
        """
        self._lock_workflow_versions(workflow_id)
        current = await self._get_latest_version(workflow_id)
        new_version_num = (current.version + 1) if current else 1
        
        version = WorkflowVersion(
            id=str(uuid4()),
            workflow_id=workflow_id,
            version=new_version_num,
            spec=workflow_spec,
            changelog=changelog,
            status="draft",
            created_by=created_by,
        )
        
        self.db.add(version)
        self.db.commit()
        
        logger.info(
            "Created version %d for workflow %s (id=%s)",
            new_version_num,
            workflow_id,
            version.id,
        )
        
        return version.id
    
    async def deploy_version(
        self,
        version_id: str,
        strategy: str = "canary",
    ) -> Dict[str, Any]:
        """Deploy a workflow version.
        
        Parameters
        ----------
        version_id : str
            ID of the version to deploy.
        strategy : str
            Deployment strategy: "canary", "blue_green", or "full".
        
        Returns
        -------
        Dict[str, Any]
            Deployment information.
        """
        version = await self._get_version(version_id)
        
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        if version.status != "draft":
            raise ValueError(f"Version {version_id} is not in draft status")
        
        if strategy == "canary":
            return await self._canary_deploy(version)
        elif strategy == "blue_green":
            return await self._blue_green_deploy(version)
        else:
            return await self._full_deploy(version)
    
    async def _canary_deploy(self, version: WorkflowVersion) -> Dict[str, Any]:
        """Deploy with canary strategy (5% → 25% → 100%).
        
        Parameters
        ----------
        version : WorkflowVersion
            The version to deploy.
        
        Returns
        -------
        Dict[str, Any]
            Deployment information.
        """
        deployment = CanaryDeployment(
            id=str(uuid4()),
            version_id=version.id,
            workflow_id=version.workflow_id,
            current_stage=0,
            current_traffic=0.05,
            status="canary_5%",
            stages=DEFAULT_STAGES,
            rollback_triggers=DEFAULT_ROLLBACK_TRIGGERS,
            started_at=datetime.now(UTC),
        )
        
        self.db.add(deployment)
        
        version.status = "published"
        version.published_at = datetime.now(UTC)
        
        self.db.commit()
        
        logger.info(
            "Started canary deployment for version %s (5%% traffic)",
            version.id,
        )
        
        return {
            "deployment_id": deployment.id,
            "version_id": version.id,
            "status": "canary_5%",
            "traffic": 0.05,
        }
    
    async def _blue_green_deploy(self, version: WorkflowVersion) -> Dict[str, Any]:
        """Deploy with blue-green strategy.
        
        Parameters
        ----------
        version : WorkflowVersion
            The version to deploy.
        
        Returns
        -------
        Dict[str, Any]
            Deployment information.
        """
        version.status = "published"
        version.published_at = datetime.now(UTC)
        
        self.db.commit()
        
        logger.info("Published version %s (blue-green)", version.id)
        
        return {
            "version_id": version.id,
            "status": "published",
            "strategy": "blue_green",
        }
    
    async def _full_deploy(self, version: WorkflowVersion) -> Dict[str, Any]:
        """Deploy with full rollout strategy.
        
        Parameters
        ----------
        version : WorkflowVersion
            The version to deploy.
        
        Returns
        -------
        Dict[str, Any]
            Deployment information.
        """
        version.status = "published"
        version.published_at = datetime.now(UTC)
        
        self.db.commit()
        
        logger.info("Published version %s (full rollout)", version.id)
        
        return {
            "version_id": version.id,
            "status": "published",
            "strategy": "full",
        }
    
    async def advance_canary(self, deployment_id: str) -> Dict[str, Any]:
        """Advance a canary deployment to the next stage.
        
        Parameters
        ----------
        deployment_id : str
            ID of the deployment to advance.
        
        Returns
        -------
        Dict[str, Any]
            Updated deployment information.
        """
        deployment = self.db.get(CanaryDeployment, deployment_id)
        
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        stages = deployment.stages or DEFAULT_STAGES
        
        if deployment.current_stage >= len(stages) - 1:
            deployment.status = "completed"
            deployment.completed_at = datetime.now(UTC)
            self.db.commit()
            
            logger.info("Canary deployment %s completed", deployment_id)
            
            return {"status": "completed", "traffic": 1.0}
        
        deployment.current_stage += 1
        next_stage = stages[deployment.current_stage]
        deployment.current_traffic = next_stage["traffic"]
        deployment.status = f"canary_{int(deployment.current_traffic * 100)}%"
        
        self.db.commit()
        
        logger.info(
            "Advanced canary deployment %s to stage %d (%d%% traffic)",
            deployment_id,
            deployment.current_stage,
            int(deployment.current_traffic * 100),
        )
        
        return {
            "status": deployment.status,
            "traffic": deployment.current_traffic,
            "stage": deployment.current_stage,
        }
    
    async def rollback(
        self,
        workflow_id: str,
        target_version: int,
        reason: str = "Manual rollback",
    ) -> Dict[str, Any]:
        """Rollback to a specific version.
        
        Parameters
        ----------
        workflow_id : str
            ID of the workflow.
        target_version : int
            Version number to rollback to.
        reason : str
            Reason for rollback.
        
        Returns
        -------
        Dict[str, Any]
            Rollback information.
        """
        current = await self._get_latest_published_version(workflow_id)
        target = await self._get_version_by_number(workflow_id, target_version)
        
        if not current:
            raise ValueError(f"No published version found for workflow {workflow_id}")
        
        if not target:
            raise ValueError(f"Version {target_version} not found for workflow {workflow_id}")
        
        current.status = "archived"
        target.status = "published"
        
        active_deployment = await self._get_active_deployment(workflow_id)
        if active_deployment:
            active_deployment.status = "rolled_back"
            active_deployment.rolled_back_at = datetime.now(UTC)
            active_deployment.rollback_reason = reason
        
        self.db.commit()
        
        logger.warning(
            "Rolled back workflow %s from version %d to %d: %s",
            workflow_id,
            current.version,
            target_version,
            reason,
        )
        
        return {
            "rolled_back_from": current.version,
            "rolled_back_to": target_version,
            "reason": reason,
        }
    
    async def check_rollback_triggers(
        self,
        deployment_id: str,
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check if any rollback triggers are hit.
        
        Parameters
        ----------
        deployment_id : str
            ID of the deployment to check.
        metrics : Dict[str, Any]
            Current metrics for the deployment.
        
        Returns
        -------
        Dict[str, Any]
            Check results.
        """
        deployment = self.db.get(CanaryDeployment, deployment_id)
        
        if not deployment:
            raise ValueError(f"Deployment {deployment_id} not found")
        
        triggers_hit = []
        
        for trigger in deployment.rollback_triggers or DEFAULT_ROLLBACK_TRIGGERS:
            metric_name = trigger["metric"]
            threshold = trigger["threshold"]
            
            current_value = metrics.get(metric_name)
            
            if current_value is None:
                continue
            
            if self._check_threshold(
                current_value,
                threshold,
                metrics,
                metric_name=metric_name,
            ):
                triggers_hit.append({
                    "metric": metric_name,
                    "threshold": threshold,
                    "current_value": current_value,
                })
        
        if triggers_hit:
            logger.warning(
                "Rollback triggers hit for deployment %s: %s",
                deployment_id,
                triggers_hit,
            )
            
            await self.rollback(
                deployment.workflow_id,
                await self._get_previous_version_number(deployment.workflow_id),
                reason=f"Automatic rollback: {triggers_hit[0]['metric']} exceeded threshold",
            )
            
            return {
                "rollback_triggered": True,
                "triggers_hit": triggers_hit,
            }
        
        return {
            "rollback_triggered": False,
            "triggers_hit": [],
        }
    
    def _check_threshold(
        self,
        current_value: float,
        threshold: str,
        metrics: Dict[str, Any],
        *,
        metric_name: str | None = None,
    ) -> bool:
        """Check if a value exceeds a threshold.
        
        Parameters
        ----------
        current_value : float
            Current metric value.
        threshold : str
            Threshold string (e.g., "2x_baseline", "5000ms", "90%").
        metrics : Dict[str, Any]
            All metrics (for baseline comparison).
        
        Returns
        -------
        bool
            True if threshold is exceeded.
        """
        if "x_baseline" in threshold:
            multiplier = float(threshold.replace("x_baseline", ""))
            baseline_metrics = metrics.get("baseline", {})
            if metric_name is not None and metric_name in baseline_metrics:
                baseline = baseline_metrics[metric_name]
            else:
                baseline = next(iter(baseline_metrics.values()), 1.0)
            return current_value > baseline * multiplier
        
        if threshold.endswith("ms"):
            threshold_ms = float(threshold[:-2])
            return current_value > threshold_ms
        
        if threshold.endswith("%"):
            threshold_pct = float(threshold[:-1])
            return current_value < threshold_pct
        
        return current_value > float(threshold)
    
    async def get_version_history(
        self,
        workflow_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get version history for a workflow.
        
        Parameters
        ----------
        workflow_id : str
            ID of the workflow.
        limit : int
            Maximum number of versions to return.
        
        Returns
        -------
        List[Dict[str, Any]]
            List of version records.
        """
        versions = (
            self.db.query(WorkflowVersion)
            .filter(WorkflowVersion.workflow_id == workflow_id)
            .order_by(desc(WorkflowVersion.version))
            .limit(limit)
            .all()
        )
        
        return [v.to_dict() for v in versions]
    
    async def _get_version(self, version_id: str) -> Optional[WorkflowVersion]:
        """Get a version by ID."""
        return self.db.get(WorkflowVersion, version_id)
    
    async def _get_latest_version(self, workflow_id: str) -> Optional[WorkflowVersion]:
        """Get the latest version for a workflow."""
        return (
            self.db.query(WorkflowVersion)
            .filter(WorkflowVersion.workflow_id == workflow_id)
            .order_by(desc(WorkflowVersion.version))
            .first()
        )
    
    async def _get_latest_published_version(
        self,
        workflow_id: str,
    ) -> Optional[WorkflowVersion]:
        """Get the latest published version for a workflow."""
        return (
            self.db.query(WorkflowVersion)
            .filter(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.status == "published",
            )
            .order_by(desc(WorkflowVersion.version))
            .first()
        )
    
    async def _get_version_by_number(
        self,
        workflow_id: str,
        version: int,
    ) -> Optional[WorkflowVersion]:
        """Get a specific version by number."""
        return (
            self.db.query(WorkflowVersion)
            .filter(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.version == version,
            )
            .first()
        )
    
    async def _get_previous_version_number(
        self,
        workflow_id: str,
    ) -> int:
        """Get the previous published version number."""
        current = await self._get_latest_published_version(workflow_id)
        if not current:
            return 1
        
        previous = (
            self.db.query(WorkflowVersion)
            .filter(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.version < current.version,
                WorkflowVersion.status.in_(["published", "archived"]),
            )
            .order_by(desc(WorkflowVersion.version))
            .first()
        )
        
        return previous.version if previous else 1
    
    async def _get_active_deployment(
        self,
        workflow_id: str,
    ) -> Optional[CanaryDeployment]:
        """Get the active deployment for a workflow."""
        return (
            self.db.query(CanaryDeployment)
            .filter(
                CanaryDeployment.workflow_id == workflow_id,
                CanaryDeployment.status.in_(["pending", "canary_5%", "canary_25%"]),
            )
            .first()
        )
