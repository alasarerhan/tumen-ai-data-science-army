"""SLA-based escalation manager for HITL approvals.

This module manages SLA-based escalation for human-in-the-loop approvals,
including reminder scheduling and automatic escalation.

Best Practices Reference:
https://harnessengineering.academy/blog/human-in-the-loop-agent-patterns-when-agents-should-ask-for-help/
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from platform_api.hitl.models import ApprovalRequest, SLAConfig

logger = logging.getLogger(__name__)


class SLAEscalationManager:
    """Manage SLA-based escalation for HITL approvals.
    
    This class handles:
    - Scheduling reminders at 50% of SLA timeout
    - Scheduling escalation at 100% of SLA timeout
    - Auto-rejecting approvals that exceed max escalation
    
    Example
    -------
    >>> manager = SLAEscalationManager()
    >>> await manager.schedule_escalation(
    ...     approval_id="approval-123",
    ...     sla_config=SLAConfig.from_urgency("high"),
    ... )
    """
    
    DEFAULT_SLA_CONFIGS = {
        "high": {"timeout": "2h", "escalation_path": ["backup", "manager", "admin"]},
        "medium": {"timeout": "8h", "escalation_path": ["backup", "manager"]},
        "low": {"timeout": "24h", "escalation_path": ["manager"]},
    }
    
    def parse_timeout(self, timeout: str) -> int:
        """Parse a timeout string to seconds.
        
        Parameters
        ----------
        timeout : str
            Timeout string (e.g., "2h", "8h", "24h").
        
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
            if timeout.endswith(unit):
                value = int(timeout[:-1])
                return value * multiplier
        
        return int(timeout)
    
    async def schedule_escalation(
        self,
        approval_id: str,
        sla_config: SLAConfig,
    ) -> None:
        """Schedule escalation triggers for an approval.
        
        Parameters
        ----------
        approval_id : str
            The approval request ID.
        sla_config : SLAConfig
            The SLA configuration.
        """
        from platform_api.services.task_scheduler import schedule_task
        
        timeout_seconds = self.parse_timeout(sla_config.timeout)
        
        await schedule_task(
            task_name="hitl_reminder",
            task_id=f"{approval_id}:reminder",
            delay_seconds=int(timeout_seconds * 0.5),
            payload={
                "approval_id": approval_id,
                "action": "reminder",
            },
        )
        
        await schedule_task(
            task_name="hitl_escalation",
            task_id=f"{approval_id}:escalation",
            delay_seconds=timeout_seconds,
            payload={
                "approval_id": approval_id,
                "action": "escalate",
                "escalate_to": sla_config.escalation_path[0] if sla_config.escalation_path else None,
            },
        )
        
        logger.info(
            "Scheduled escalation for approval %s (timeout=%s, path=%s)",
            approval_id,
            sla_config.timeout,
            sla_config.escalation_path,
        )
    
    async def handle_timeout(self, approval_id: str) -> None:
        """Handle SLA timeout for an approval.
        
        This method is called when an approval's SLA expires.
        It will either escalate or auto-reject based on the
        current escalation level.
        
        Parameters
        ----------
        approval_id : str
            The approval request ID.
        """
        approval = await self._get_approval(approval_id)
        
        if not approval:
            logger.warning("Approval %s not found for timeout handling", approval_id)
            return
        
        if approval.status != "pending":
            logger.info("Approval %s is no longer pending (status=%s)", approval_id, approval.status)
            return
        
        max_escalation = len(approval.escalation_path)
        
        if approval.escalation_level >= max_escalation:
            await self._auto_reject(approval, reason="SLA timeout - max escalation reached")
        else:
            await self._escalate(approval)
    
    async def handle_reminder(self, approval_id: str) -> None:
        """Handle reminder trigger for an approval.
        
        Parameters
        ----------
        approval_id : str
            The approval request ID.
        """
        approval = await self._get_approval(approval_id)
        
        if not approval or approval.status != "pending":
            return
        
        await self._send_reminder(approval)
    
    async def _escalate(self, approval: ApprovalRequest) -> None:
        """Escalate an approval to the next level.
        
        Parameters
        ----------
        approval : ApprovalRequest
            The approval request to escalate.
        """
        approval.escalation_level += 1
        
        next_level = approval.escalation_path[approval.escalation_level - 1] if approval.escalation_level <= len(approval.escalation_path) else "admin"
        
        logger.info(
            "Escalating approval %s to level %d (%s)",
            approval.id,
            approval.escalation_level,
            next_level,
        )
        
        from platform_api.hitl.notification_router import HITLNotificationRouter
        router = HITLNotificationRouter()
        
        await router.route_approval_request(
            approval,
            {
                "default_channel": "chat",
                "escalation_level": approval.escalation_level,
                "escalated_to": next_level,
            },
        )
        
        await self._save_approval(approval)
    
    async def _auto_reject(
        self,
        approval: ApprovalRequest,
        reason: str,
    ) -> None:
        """Auto-reject an approval.
        
        Parameters
        ----------
        approval : ApprovalRequest
            The approval request to reject.
        reason : str
            The reason for auto-rejection.
        """
        approval.status = "rejected"
        approval.decision = "auto_rejected"
        approval.notes = reason
        approval.decision_at = datetime.utcnow()
        
        logger.warning(
            "Auto-rejected approval %s: %s",
            approval.id,
            reason,
        )
        
        await self._save_approval(approval)
        
        await self._notify_auto_rejection(approval, reason)
    
    async def _send_reminder(self, approval: ApprovalRequest) -> None:
        """Send a reminder for a pending approval.
        
        Parameters
        ----------
        approval : ApprovalRequest
            The approval request.
        """
        from platform_api.hitl.notification_router import HITLNotificationRouter
        router = HITLNotificationRouter()
        
        reminder_request = ApprovalRequest(
            id=approval.id,
            workflow_run_id=approval.workflow_run_id,
            step_id=approval.step_id,
            agent_name=approval.agent_name,
            title=f"[Reminder] {approval.title}",
            content=f"This approval is still pending. Please review.\n\n{approval.content}",
            context=approval.context,
            urgency=approval.urgency,
            sla_timeout=approval.sla_timeout,
            escalation_path=approval.escalation_path,
            created_at=approval.created_at,
            status=approval.status,
            escalation_level=approval.escalation_level,
        )
        
        await router.route_approval_request(reminder_request, {"is_reminder": True})
        
        logger.info("Sent reminder for approval %s", approval.id)
    
    async def _notify_auto_rejection(
        self,
        approval: ApprovalRequest,
        reason: str,
    ) -> None:
        """Notify about auto-rejection.
        
        Parameters
        ----------
        approval : ApprovalRequest
            The auto-rejected approval.
        reason : str
            The reason for auto-rejection.
        """
        from platform_api.hitl.notification_router import HITLNotificationRouter
        router = HITLNotificationRouter()
        
        notification_request = ApprovalRequest(
            id=approval.id,
            workflow_run_id=approval.workflow_run_id,
            step_id=approval.step_id,
            agent_name=approval.agent_name,
            title=f"[Auto-Rejected] {approval.title}",
            content=f"This approval was automatically rejected.\n\nReason: {reason}",
            context=approval.context,
            urgency="high",
            sla_timeout="0h",
            escalation_path=[],
            created_at=approval.created_at,
            status="rejected",
            decision="auto_rejected",
            notes=reason,
        )
        
        await router.route_approval_request(notification_request, {"is_auto_rejection": True})
    
    async def _get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get an approval by ID.
        
        Parameters
        ----------
        approval_id : str
            The approval request ID.
        
        Returns
        -------
        Optional[ApprovalRequest]
            The approval request, or None if not found.
        """
        from platform_api.services.hitl_service import get_approval_request
        return await get_approval_request(approval_id)
    
    async def _save_approval(self, approval: ApprovalRequest) -> None:
        """Save an approval.
        
        Parameters
        ----------
        approval : ApprovalRequest
            The approval request to save.
        """
        from platform_api.services.hitl_service import update_approval_request
        await update_approval_request(approval.id, approval.to_dict())
    
    def get_sla_status(
        self,
        approval: ApprovalRequest,
    ) -> Dict[str, Any]:
        """Get the SLA status for an approval.
        
        Parameters
        ----------
        approval : ApprovalRequest
            The approval request.
        
        Returns
        -------
        Dict[str, Any]
            SLA status information.
        """
        sla_config = SLAConfig.from_urgency(approval.urgency)
        timeout_seconds = self.parse_timeout(sla_config.timeout)
        
        elapsed = (datetime.utcnow() - approval.created_at).total_seconds()
        remaining = max(0, timeout_seconds - elapsed)
        percentage = min(100, (elapsed / timeout_seconds) * 100)
        
        return {
            "approval_id": approval.id,
            "urgency": approval.urgency,
            "timeout_seconds": timeout_seconds,
            "elapsed_seconds": elapsed,
            "remaining_seconds": remaining,
            "percentage_used": round(percentage, 1),
            "is_overdue": remaining == 0,
            "escalation_level": approval.escalation_level,
            "max_escalation": len(approval.escalation_path),
        }
