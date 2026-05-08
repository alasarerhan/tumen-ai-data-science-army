"""HITL (Human-in-the-Loop) module for approval workflows.

This module provides:
- Approval request models
- Multi-channel notification routing
- SLA-based escalation management
"""

from platform_api.hitl.models import ApprovalRequest, SLAConfig
from platform_api.hitl.notification_router import HITLNotificationRouter, NotificationChannel
from platform_api.hitl.escalation_manager import SLAEscalationManager

__all__ = [
    "ApprovalRequest",
    "SLAConfig",
    "HITLNotificationRouter",
    "NotificationChannel",
    "SLAEscalationManager",
]
