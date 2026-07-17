"""Workflow versioning models.

This module defines the database models for workflow versioning
and canary deployments.

Best Practices Reference:
https://zylos.ai/research/2026-03-06-ai-agent-version-management-safe-upgrade-patterns
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from platform_api.db.base import Base


class WorkflowVersion(Base):
    """Represents a version of a workflow specification.
    
    Attributes
    ----------
    id : str
        Unique identifier for the version.
    workflow_id : str
        ID of the parent workflow.
    version : int
        Version number (auto-incremented per workflow).
    spec : dict
        The workflow specification JSON.
    changelog : str, optional
        Description of changes in this version.
    status : str
        Version status: "draft", "published", "archived".
    created_at : datetime
        When the version was created.
    published_at : datetime, optional
        When the version was published.
    created_by : str, optional
        User ID who created this version.
    """
    
    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_version"),
    )
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(36), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    changelog: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[str]] = mapped_column(String(36))
    
    deployment: Mapped[Optional["CanaryDeployment"]] = relationship(
        back_populates="version",
        uselist=False,
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "version": self.version,
            "spec": self.spec,
            "changelog": self.changelog,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_by": self.created_by,
        }


class CanaryDeployment(Base):
    """Represents a canary deployment for a workflow version.
    
    Canary deployments gradually roll out a new version:
    - Stage 0: 5% traffic for 24h
    - Stage 1: 25% traffic for 24h
    - Stage 2: 100% traffic
    
    Attributes
    ----------
    id : str
        Unique identifier for the deployment.
    version_id : str
        ID of the workflow version being deployed.
    workflow_id : str
        ID of the parent workflow.
    current_stage : int
        Current canary stage (0, 1, 2).
    current_traffic : float
        Current traffic percentage (0.05, 0.25, 1.0).
    status : str
        Deployment status: "pending", "canary_5%", "canary_25%", "completed", "rolled_back".
    stages : dict
        Configuration for each stage.
    rollback_triggers : dict
        Conditions that trigger automatic rollback.
    created_at : datetime
        When the deployment was created.
    started_at : datetime, optional
        When the deployment started.
    completed_at : datetime, optional
        When the deployment completed.
    rolled_back_at : datetime, optional
        When the deployment was rolled back.
    rollback_reason : str, optional
        Reason for rollback.
    """
    
    __tablename__ = "canary_deployments"
    __table_args__ = (
        UniqueConstraint("version_id", name="uq_canary_deployments_version_id"),
    )
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        index=True,
        unique=True,
    )
    workflow_id: Mapped[str] = mapped_column(String(36), index=True)
    current_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_traffic: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    stages: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    rollback_triggers: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rollback_reason: Mapped[Optional[str]] = mapped_column(Text)
    
    version: Mapped["WorkflowVersion"] = relationship(back_populates="deployment")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "version_id": self.version_id,
            "workflow_id": self.workflow_id,
            "current_stage": self.current_stage,
            "current_traffic": self.current_traffic,
            "status": self.status,
            "stages": self.stages,
            "rollback_triggers": self.rollback_triggers,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "rolled_back_at": self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            "rollback_reason": self.rollback_reason,
        }


DEFAULT_STAGES = [
    {
        "stage": 0,
        "traffic": 0.05,
        "duration": "24h",
        "gates": ["error_rate < 2x_baseline", "success_rate > 95%"],
    },
    {
        "stage": 1,
        "traffic": 0.25,
        "duration": "24h",
        "gates": ["error_rate < 1.5x_baseline", "success_rate > 97%"],
    },
    {
        "stage": 2,
        "traffic": 1.0,
        "duration": "7d",
        "gates": ["all_metrics_ok"],
    },
]

DEFAULT_ROLLBACK_TRIGGERS = [
    {"metric": "error_rate", "threshold": "2x_baseline", "window": "15m"},
    {"metric": "latency_p95", "threshold": "5000ms", "window": "10m"},
    {"metric": "success_rate", "threshold": "90%", "window": "15m"},
    {"metric": "token_usage", "threshold": "1.3x_baseline", "window": "30m"},
]
