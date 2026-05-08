"""HITL notification router for multi-channel approval routing.

This module routes approval requests to appropriate notification channels
based on urgency, user preferences, and task type.

Best Practices Reference:
https://www.moxo.com/blog/designing-human-checkpoints-in-hitl-workflow
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional

from platform_api.hitl.models import ApprovalRequest

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Available notification channels for HITL approvals."""
    
    CHAT = "chat"
    EMAIL = "email"
    FORM = "form"


class HITLNotificationRouter:
    """Route HITL approvals to appropriate channels.
    
    This class determines the best notification channel for an approval
    request based on urgency, user preferences, and task type.
    
    Example
    -------
    >>> router = HITLNotificationRouter()
    >>> notification_id = await router.route_approval_request(
    ...     approval_request=request,
    ...     user_preferences={"default_channel": "chat"},
    ... )
    """
    
    async def route_approval_request(
        self,
        approval_request: ApprovalRequest,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Route an approval request to the appropriate channel.
        
        Parameters
        ----------
        approval_request : ApprovalRequest
            The approval request to route.
        user_preferences : Optional[Dict[str, Any]]
            User's notification preferences.
        
        Returns
        -------
        str
            The notification ID for tracking.
        """
        preferences = user_preferences or {}
        
        channel = self._determine_channel(approval_request, preferences)
        
        logger.info(
            "Routing approval %s to channel %s (urgency=%s)",
            approval_request.id,
            channel.value,
            approval_request.urgency,
        )
        
        if channel == NotificationChannel.CHAT:
            return await self._send_chat_notification(approval_request)
        elif channel == NotificationChannel.EMAIL:
            return await self._send_email_notification(approval_request)
        else:
            return await self._send_form_notification(approval_request)
    
    def _determine_channel(
        self,
        request: ApprovalRequest,
        preferences: Dict[str, Any],
    ) -> NotificationChannel:
        """Determine the best notification channel.
        
        Parameters
        ----------
        request : ApprovalRequest
            The approval request.
        preferences : Dict[str, Any]
            User's notification preferences.
        
        Returns
        -------
        NotificationChannel
            The selected notification channel.
        """
        if request.urgency == "high":
            return NotificationChannel.CHAT
        
        preferred = preferences.get("default_channel", "chat")
        
        if preferred in ["chat", "email", "form"]:
            return NotificationChannel(preferred)
        
        return NotificationChannel.CHAT
    
    async def _send_chat_notification(
        self,
        request: ApprovalRequest,
    ) -> str:
        """Send notification via chat interface.
        
        Parameters
        ----------
        request : ApprovalRequest
            The approval request.
        
        Returns
        -------
        str
            The notification ID.
        """
        from platform_api.services.chat_service import send_system_message
        
        message = self._build_approval_message(request)
        
        notification_id = await send_system_message(
            session_id=request.context.get("chat_session_id"),
            content=message,
            metadata={
                "type": "approval_request",
                "approval_id": request.id,
                "workflow_run_id": request.workflow_run_id,
                "step_id": request.step_id,
                "urgency": request.urgency,
                "sla_timeout": request.sla_timeout,
                "buttons": ["Approve", "Reject", "Modify"],
            },
        )
        
        logger.info("Sent chat notification %s for approval %s", notification_id, request.id)
        
        return notification_id
    
    async def _send_email_notification(
        self,
        request: ApprovalRequest,
    ) -> str:
        """Send notification via email.
        
        Parameters
        ----------
        request : ApprovalRequest
            The approval request.
        
        Returns
        -------
        str
            The notification ID.
        """
        from platform_api.services.email_service import send_email
        
        subject = f"[Approval Required] {request.title}"
        body = self._build_email_body(request)
        
        notification_id = await send_email(
            to=request.context.get("reviewer_email"),
            subject=subject,
            body=body,
            metadata={
                "approval_id": request.id,
                "workflow_run_id": request.workflow_run_id,
            },
        )
        
        logger.info("Sent email notification %s for approval %s", notification_id, request.id)
        
        return notification_id
    
    async def _send_form_notification(
        self,
        request: ApprovalRequest,
    ) -> str:
        """Send notification via form interface.
        
        Parameters
        ----------
        request : ApprovalRequest
            The approval request.
        
        Returns
        -------
        str
            The notification ID.
        """
        notification_id = f"form-{request.id}"
        
        logger.info("Created form notification %s for approval %s", notification_id, request.id)
        
        return notification_id
    
    def _build_approval_message(self, request: ApprovalRequest) -> str:
        """Build the approval message for chat.
        
        Parameters
        ----------
        request : ApprovalRequest
            The approval request.
        
        Returns
        -------
        str
            The formatted message.
        """
        return f"""**Approval Required: {request.title}**

{request.content}

**Context:**
- Workflow: {request.workflow_run_id}
- Step: {request.step_id}
- Agent: {request.agent_name}
- Urgency: {request.urgency}
- SLA: {request.sla_timeout}

Please review and respond within the SLA timeframe."""
    
    def _build_email_body(self, request: ApprovalRequest) -> str:
        """Build the email body for approval.
        
        Parameters
        ----------
        request : ApprovalRequest
            The approval request.
        
        Returns
        -------
        str
            The formatted email body.
        """
        return f"""
Approval Required: {request.title}

{request.content}

Workflow: {request.workflow_run_id}
Step: {request.step_id}
Agent: {request.agent_name}
Urgency: {request.urgency}
SLA: {request.sla_timeout}

Please review and respond within the SLA timeframe.

---
This is an automated message from the AI Data Science Team platform.
"""
