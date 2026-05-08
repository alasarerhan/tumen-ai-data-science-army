from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_api.auth.models import Principal
from platform_api.db.models import TenantMembership, User, WorkspaceMembership
from platform_api.core.service_errors import ConflictError


def normalize_email(email: Optional[str]) -> Optional[str]:
    """Normalize an email address for consistent storage and comparison.
    
    - Converts to lowercase
    - Strips leading/trailing whitespace
    - Returns None for empty strings or None
    
    Per RFC 5321, the local part of an email is case-sensitive, but in practice
    most email providers treat it as case-insensitive. We normalize to lowercase
    for consistency and to prevent duplicate accounts.
    
    Parameters
    ----------
    email : str | None
        The email address to normalize.
    
    Returns
    -------
    str | None
        The normalized email address, or None if input was None/empty.
    """
    if email is None:
        return None
    email = email.strip()
    if not email:
        return None
    return email.lower()


def validate_email_format(email: str) -> bool:
    """Basic email format validation.
    
    This is a simple check, not a full RFC 5322 validation.
    For production, consider using a library like email-validator.
    
    Parameters
    ----------
    email : str
        The email address to validate.
    
    Returns
    -------
    bool
        True if the email appears valid, False otherwise.
    """
    if not email or len(email) > 320:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def get_or_create_user(db: Session, principal: Principal) -> User:
    normalized_email = normalize_email(principal.email)
    user = db.execute(select(User).where(User.sub == principal.sub)).scalar_one_or_none()
    if normalized_email:
        email_owner = db.execute(select(User).where(User.email == normalized_email)).scalar_one_or_none()
        if email_owner is not None and email_owner.sub != principal.sub:
            raise ConflictError("Email address is already linked to another account")
    if user is None:
        user = User(sub=principal.sub, email=normalized_email)
        db.add(user)
        db.flush()
    elif normalized_email and user.email != normalized_email:
        user.email = normalized_email
        db.add(user)

    return user


def list_tenant_memberships(db: Session, user_id) -> list[TenantMembership]:
    return list(
        db.execute(
            select(TenantMembership).where(TenantMembership.user_id == user_id)
        ).scalars()
    )


def list_workspace_memberships(db: Session, user_id) -> list[WorkspaceMembership]:
    return list(
        db.execute(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == user_id)
        ).scalars()
    )
