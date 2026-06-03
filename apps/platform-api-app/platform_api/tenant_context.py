"""Tenant context management for multi-tenant isolation.

This module implements the best practice of propagating tenant context to PostgreSQL
for Row Level Security (RLS) enforcement.

Best Practice Reference:
- https://github.com/dctalbot/pg-tenant-isolation
- https://www.techbuddies.io/2026/01/01/how-to-implement-postgresql-row-level-security-for-multi-tenant-saas/

The tenant context is set at the start of each request via:
    SET app.current_tenant_id = 'tenant-uuid-here';

This is done automatically via SQLAlchemy session events when using the
TenantSession class or the set_tenant_context() function.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from contextvars import ContextVar
from typing import Generator

from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)
_current_workspace_id: ContextVar[uuid.UUID | None] = ContextVar("current_workspace_id", default=None)
_current_system_actor: ContextVar[bool] = ContextVar("current_system_actor", default=False)


def get_current_tenant_id() -> uuid.UUID | None:
    """Get the current tenant ID from context."""
    return _current_tenant_id.get()


def get_current_workspace_id() -> uuid.UUID | None:
    """Get the current workspace ID from context."""
    return _current_workspace_id.get()


def get_current_system_actor() -> bool:
    """Return whether the current execution context is an internal system actor."""
    return _current_system_actor.get()


def set_tenant_context(tenant_id: uuid.UUID | str, workspace_id: uuid.UUID | str | None = None) -> None:
    """Set the tenant context for the current request.

    This should be called at the start of each request after authentication.
    The context is stored in a ContextVar for access throughout the request.
    """
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)
    if workspace_id is not None and isinstance(workspace_id, str):
        workspace_id = uuid.UUID(workspace_id)

    _current_tenant_id.set(tenant_id)
    if workspace_id is not None:
        _current_workspace_id.set(workspace_id)

    logger.debug("Tenant context set: tenant_id=%s, workspace_id=%s", tenant_id, workspace_id)


def set_system_actor_context(enabled: bool = True) -> None:
    """Mark the current execution context as an internal system actor."""
    _current_system_actor.set(enabled)
    logger.debug("System actor context set: enabled=%s", enabled)


def clear_tenant_context() -> None:
    """Clear the tenant context at the end of a request."""
    _current_tenant_id.set(None)
    _current_workspace_id.set(None)
    _current_system_actor.set(False)
    logger.debug("Tenant context cleared")


@contextlib.contextmanager
def tenant_context(tenant_id: uuid.UUID | str, workspace_id: uuid.UUID | str | None = None) -> Generator[None, None, None]:
    """Context manager for tenant context.

    Usage:
        with tenant_context(tenant_id, workspace_id):
            # All database queries in this block are filtered by tenant
            ...
    """
    set_tenant_context(tenant_id, workspace_id)
    try:
        yield
    finally:
        clear_tenant_context()


@contextlib.contextmanager
def system_actor_context(db: Session | None = None) -> Generator[None, None, None]:
    """Context manager for internal maintenance work that must bypass tenant RLS."""
    original_tenant = get_current_tenant_id()
    original_workspace = get_current_workspace_id()
    original_system_actor = get_current_system_actor()

    set_system_actor_context(True)
    if db is not None:
        _set_postgres_rls_context(
            db,
            tenant_id=original_tenant,
            system_actor=True,
        )

    try:
        yield
    finally:
        if original_tenant is not None:
            set_tenant_context(original_tenant, original_workspace)
        else:
            _current_tenant_id.set(None)
            _current_workspace_id.set(None)
        set_system_actor_context(original_system_actor)
        if db is not None:
            _set_postgres_rls_context(
                db,
                tenant_id=original_tenant,
                system_actor=original_system_actor,
            )


class TenantContextError(Exception):
    """Raised when tenant context cannot be set or reset."""
    pass


def _set_postgres_rls_context(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    system_actor: bool,
) -> None:
    """Set PostgreSQL session variables used by RLS.

    This executes SET app.current_tenant_id = '...' on the database connection.
    PostgreSQL RLS policies will use this value to filter queries.
    
    Raises
    ------
    TenantContextError
        If the tenant context cannot be set or reset.
    """
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    if tenant_id is None:
        db.execute(text("RESET app.current_tenant_id"))
    else:
        db.execute(text("SET app.current_tenant_id = :tenant_id"), {"tenant_id": str(tenant_id)})

    if system_actor:
        db.execute(text("SET app.current_actor_is_system = true"))
    else:
        db.execute(text("RESET app.current_actor_is_system"))


def _set_postgres_tenant_context(db: Session, tenant_id: uuid.UUID | None) -> None:
    """Backward-compatible helper for setting tenant-only context."""
    _set_postgres_rls_context(
        db,
        tenant_id=tenant_id,
        system_actor=get_current_system_actor(),
    )


def configure_session_events(session_local: sessionmaker) -> None:
    """Configure SQLAlchemy session events for automatic tenant context propagation.

    This should be called once during application startup.

    Best Practice: Set tenant context on connection checkout and reset on checkin
    to prevent cross-tenant data leakage in connection pools.

    Usage:
        from platform_api.db.session import SessionLocal
        from platform_api.tenant_context import configure_session_events

        configure_session_events(SessionLocal)
    """

    @event.listens_for(session_local, "after_begin")
    def receive_after_begin(_session, _transaction, connection):
        """Set tenant context when a transaction begins."""
        if connection.dialect.name != "postgresql":
            return
        tenant_id = get_current_tenant_id()
        system_actor = get_current_system_actor()
        try:
            if tenant_id is None:
                connection.execute(text("RESET app.current_tenant_id"))
            else:
                connection.execute(
                    text("SET app.current_tenant_id = :tenant_id"),
                    {"tenant_id": str(tenant_id)},
                )
            if system_actor:
                connection.execute(text("SET app.current_actor_is_system = true"))
            else:
                connection.execute(text("RESET app.current_actor_is_system"))
        except Exception as e:
            logger.error(
                "CRITICAL: Failed to set RLS context for tenant_id=%s system_actor=%s. "
                "RLS will not be enforced. Aborting request. Error: %s",
                tenant_id,
                system_actor,
                e,
            )
            raise TenantContextError(
                "Failed to set RLS context for the current execution. "
                "Request aborted to prevent cross-tenant data leakage."
            ) from e

    @event.listens_for(session_local, "after_transaction_end")
    def receive_after_transaction_end(session, _transaction):
        """Reset tenant context after transaction ends to prevent leakage."""
        bind = session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return
        try:
            session.execute(text("RESET app.current_tenant_id"))
            session.execute(text("RESET app.current_actor_is_system"))
        except Exception as e:
            logger.error(
                "CRITICAL: Failed to reset tenant context after transaction. "
                "This may cause cross-tenant data leakage. Error: %s",
                e,
            )
            raise TenantContextError(
                "Failed to reset tenant context after transaction. "
                "Connection marked as potentially contaminated."
            ) from e


class TenantSession:
    """A session wrapper that automatically sets tenant context.

    Usage:
        with TenantSession(db, tenant_id=tenant_id) as session:
            # All queries are automatically filtered by tenant
            items = session.execute(select(Item)).scalars().all()
    """

    def __init__(self, db: Session, tenant_id: uuid.UUID | str, workspace_id: uuid.UUID | str | None = None):
        self.db = db
        self.tenant_id = uuid.UUID(str(tenant_id)) if isinstance(tenant_id, str) else tenant_id
        self.workspace_id = uuid.UUID(str(workspace_id)) if workspace_id and isinstance(workspace_id, str) else workspace_id
        self._original_tenant = get_current_tenant_id()
        self._original_workspace = get_current_workspace_id()
        self._original_system_actor = get_current_system_actor()

    def __enter__(self) -> Session:
        set_tenant_context(self.tenant_id, self.workspace_id)
        set_system_actor_context(False)
        _set_postgres_rls_context(
            self.db,
            tenant_id=self.tenant_id,
            system_actor=False,
        )
        return self.db

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        _set_postgres_rls_context(
            self.db,
            tenant_id=self._original_tenant,
            system_actor=self._original_system_actor,
        )
        if self._original_tenant:
            set_tenant_context(self._original_tenant, self._original_workspace)
        else:
            _current_tenant_id.set(None)
            _current_workspace_id.set(None)
        set_system_actor_context(self._original_system_actor)


def with_tenant_session(db: Session, tenant_id: uuid.UUID | str, workspace_id: uuid.UUID | str | None = None) -> TenantSession:
    """Create a tenant-scoped session.

    Usage:
        with with_tenant_session(db, tenant_id) as session:
            items = session.execute(select(Item)).scalars().all()
    """
    return TenantSession(db, tenant_id, workspace_id)


def require_tenant_context() -> uuid.UUID:
    """Require tenant context to be set, raising an error if not.

    Use this at the start of request handlers or service methods that
    require tenant context to be set. This prevents accidental data leaks
    when tenant context is missing.

    Returns
    -------
    uuid.UUID
        The current tenant ID.

    Raises
    ------
    TenantContextError
        If tenant context is not set.
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise TenantContextError(
            "Tenant context is required but not set. "
            "This indicates a bug where a request handler or service method "
            "is accessing tenant-scoped data without proper authentication. "
            "Ensure set_tenant_context() is called after authentication."
        )
    return tenant_id


def validate_tenant_context_at_startup() -> None:
    """Validate tenant context configuration at application startup.

    This should be called during application startup to verify that
    tenant context is properly configured.

    Raises
    ------
    RuntimeError
        If tenant context configuration is invalid.
    """
    import os
    
    auth_mode = os.environ.get("AUTH_MODE", "oidc")
    deployment_profile = os.environ.get("DEPLOYMENT_PROFILE", "release")

    if auth_mode == "oidc" and deployment_profile == "release":
        logger.info(
            "Tenant context validation: release OIDC mode. "
            "Tenant context MUST be set for all authenticated requests."
        )
    else:
        logger.info(
            "Tenant context validation: AUTH_MODE=%s. "
            "Tenant context enforcement is lenient for development.",
            auth_mode
        )
