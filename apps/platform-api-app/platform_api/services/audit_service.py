from __future__ import annotations

from sqlalchemy.orm import Session

from platform_api.db.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    actor_user_id,
    action: str,
    tenant_id=None,
    workspace_id=None,
    details: str | None = None,
) -> AuditLog:
    record = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        details=details,
    )
    db.add(record)
    db.flush()
    return record
