"""HITL models for approval requests and SLA configuration.

This module defines the data models for human-in-the-loop workflows.

Best Practices Reference:
https://harnessengineering.academy/blog/human-in-the-loop-agent-patterns-when-agents-should-ask-for-help/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ApprovalRequest:
    """Represents an approval request in a HITL workflow.

    Attributes
    ----------
    id : str
        Unique identifier for the approval request.
    workflow_run_id : str
        ID of the workflow run that created this request.
    step_id : str
        ID of the step that requires approval.
    agent_name : str
        Name of the agent that created the request.
    title : str
        Short title for the approval request.
    content : str
        Detailed content describing what needs approval.
    context : Dict[str, Any]
        Additional context for the reviewer (data, artifacts, etc.).
    urgency : str
        Priority level: "high", "medium", or "low".
    sla_timeout : str
        SLA timeout string (e.g., "2h", "8h", "24h").
    escalation_path : List[str]
        List of escalation targets (e.g., ["backup", "manager"]).
    created_at : datetime
        When the request was created.
    expires_at : Optional[datetime]
        When the request expires (if applicable).
    status : str
        Current status: "pending", "approved", "rejected", "expired".
    reviewer_id : Optional[str]
        ID of the assigned reviewer.
    decision_at : Optional[datetime]
        When the decision was made.
    decision : Optional[str]
        The decision: "approved", "rejected", "auto_approved", "auto_rejected".
    notes : Optional[str]
        Additional notes from the reviewer.
    escalation_level : int
        Current escalation level (0 = initial, 1+ = escalated).
    """

    id: str
    workflow_run_id: str
    step_id: str
    agent_name: str
    title: str
    content: str
    context: dict[str, Any] = field(default_factory=dict)
    urgency: str = "medium"
    sla_timeout: str = "8h"
    escalation_path: list[str] = field(default_factory=lambda: ["backup"])
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    status: str = "pending"
    reviewer_id: str | None = None
    decision_at: datetime | None = None
    decision: str | None = None
    notes: str | None = None
    escalation_level: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "workflow_run_id": self.workflow_run_id,
            "step_id": self.step_id,
            "agent_name": self.agent_name,
            "title": self.title,
            "content": self.content,
            "context": self.context,
            "urgency": self.urgency,
            "sla_timeout": self.sla_timeout,
            "escalation_path": self.escalation_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "status": self.status,
            "reviewer_id": self.reviewer_id,
            "decision_at": self.decision_at.isoformat() if self.decision_at else None,
            "decision": self.decision,
            "notes": self.notes,
            "escalation_level": self.escalation_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRequest:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            workflow_run_id=data["workflow_run_id"],
            step_id=data["step_id"],
            agent_name=data["agent_name"],
            title=data["title"],
            content=data["content"],
            context=data.get("context", {}),
            urgency=data.get("urgency", "medium"),
            sla_timeout=data.get("sla_timeout", "8h"),
            escalation_path=data.get("escalation_path", ["backup"]),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.utcnow(),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
            status=data.get("status", "pending"),
            reviewer_id=data.get("reviewer_id"),
            decision_at=datetime.fromisoformat(data["decision_at"])
            if data.get("decision_at")
            else None,
            decision=data.get("decision"),
            notes=data.get("notes"),
            escalation_level=data.get("escalation_level", 0),
        )


@dataclass
class SLAConfig:
    """SLA configuration for approval requests.

    Attributes
    ----------
    urgency : str
        Priority level: "high", "medium", or "low".
    timeout : str
        SLA timeout string (e.g., "2h", "8h", "24h").
    escalation_path : List[str]
        List of escalation targets.
    """

    urgency: str
    timeout: str
    escalation_path: list[str]

    @classmethod
    def from_urgency(cls, urgency: str) -> SLAConfig:
        """Create SLA config from urgency level.

        Parameters
        ----------
        urgency : str
            Priority level: "high", "medium", or "low".

        Returns
        -------
        SLAConfig
            Configured SLA settings.
        """
        configs = {
            "high": cls(
                urgency="high",
                timeout="2h",
                escalation_path=["backup", "manager", "admin"],
            ),
            "medium": cls(
                urgency="medium",
                timeout="8h",
                escalation_path=["backup", "manager"],
            ),
            "low": cls(
                urgency="low",
                timeout="24h",
                escalation_path=["manager"],
            ),
        }
        return configs.get(urgency, configs["medium"])

    def to_timeout_seconds(self) -> int:
        """Convert timeout string to seconds.

        Returns
        -------
        int
            Timeout in seconds.
        """
        unit_multipliers = {
            "h": 3600,
            "m": 60,
            "d": 86400,
        }

        for unit, multiplier in unit_multipliers.items():
            if self.timeout.endswith(unit):
                value = int(self.timeout[:-1])
                return value * multiplier

        return int(self.timeout)


@dataclass
class ApprovalResponse:
    """Response to an approval request.

    Attributes
    ----------
    approval_id : str
        ID of the approval request.
    decision : str
        The decision: "approved", "rejected", "modified".
    notes : Optional[str]
        Additional notes from the reviewer.
    modified_data : Optional[Dict[str, Any]]
        Modified data if decision is "modified".
    reviewed_at : datetime
        When the response was submitted.
    reviewer_id : str
        ID of the reviewer.
    """

    approval_id: str
    decision: str
    notes: str | None = None
    modified_data: dict[str, Any] | None = None
    reviewed_at: datetime = field(default_factory=datetime.utcnow)
    reviewer_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "approval_id": self.approval_id,
            "decision": self.decision,
            "notes": self.notes,
            "modified_data": self.modified_data,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_id": self.reviewer_id,
        }
