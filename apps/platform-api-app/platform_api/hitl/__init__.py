"""HITL (Human-in-the-Loop) module for approval workflows.

This module provides:
- Approval request models
- Multi-channel notification routing
- SLA-based escalation management
"""

from platform_api.hitl.escalation_manager import SLAEscalationManager
from platform_api.hitl.models import ApprovalRequest, SLAConfig
from platform_api.hitl.notification_router import HITLNotificationRouter, NotificationChannel

__all__ = [
    "ApprovalRequest",
    "HITLNotificationRouter",
    "NotificationChannel",
    "SLAConfig",
    "SLAEscalationManager",
]
