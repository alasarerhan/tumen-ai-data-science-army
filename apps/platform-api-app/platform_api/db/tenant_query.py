"""TenantQuery - Fluent query builder for tenant-scoped database operations.

Reduces boilerplate for multi-tenant queries by encapsulating:
- UUID parsing and validation
- Tenant/workspace filtering
- Common query patterns (get, list, exists)
- 404 handling with consistent error messages

Usage
-----
::

    from platform_api.db.tenant_query import TenantQuery

    # Simple get with tenant/workspace filtering
    run = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get(run_id)

    # List with pagination
    runs = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).list(limit=20, cursor=cursor)

    # Check existence
    exists = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).exists(run_id)

    # Get with row-level lock (for updates)
    run = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get_for_update(run_id)

Design
------
- Fluent interface: chain methods for readability
- Lazy evaluation: query is only executed when terminal method is called
- Type-safe: returns the model type, not a dict
- Consistent errors: 404 with model name in message
"""

from __future__ import annotations

import uuid
from typing import Generic, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from platform_api.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class TenantQuery(Generic[ModelType]):
    """Fluent query builder for tenant-scoped database operations.

    Encapsulates common patterns for multi-tenant queries:
    - UUID parsing and validation
    - Tenant/workspace filtering
    - Pagination with cursor
    - Row-level locking for updates

    Example
    -------
    ::

        # Get single record
        run = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get(run_id)

        # List with pagination
        runs = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).list(limit=20)

        # Get for update (with row lock)
        run = TenantQuery(db, WorkflowRun).for_workspace(workspace_id).get_for_update(run_id)
    """

    def __init__(self, db: Session, model: Type[ModelType]):
        self._db = db
        self._model = model
        self._tenant_id: uuid.UUID | None = None
        self._workspace_id: uuid.UUID | None = None
        self._model_name = model.__name__

    def for_tenant(self, tenant_id: uuid.UUID | str) -> "TenantQuery[ModelType]":
        """Set tenant filter.

        Parameters
        ----------
        tenant_id : UUID | str
            Tenant UUID or string representation.

        Returns
        -------
        TenantQuery
            Self for method chaining.
        """
        self._tenant_id = self._parse_uuid(tenant_id, "tenant_id")
        return self

    def for_workspace(self, workspace_id: uuid.UUID | str) -> "TenantQuery[ModelType]":
        """Set workspace filter.

        Parameters
        ----------
        workspace_id : UUID | str
            Workspace UUID or string representation.

        Returns
        -------
        TenantQuery
            Self for method chaining.
        """
        self._workspace_id = self._parse_uuid(workspace_id, "workspace_id")
        return self

    def get(self, id: uuid.UUID | str) -> ModelType:
        """Get a single record by ID with tenant/workspace filtering.

        Parameters
        ----------
        id : UUID | str
            Record UUID or string representation.

        Returns
        -------
        ModelType
            The database model instance.

        Raises
        ------
        HTTPException
            404 if record not found or doesn't belong to tenant/workspace.
        """
        record_uuid = self._parse_uuid(id, "id")
        stmt = select(self._model).where(self._model.id == record_uuid)
        stmt = self._apply_filters(stmt)
        result = self._db.execute(stmt).scalar_one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail=f"{self._model_name} not found")
        return result

    def get_or_none(self, id: uuid.UUID | str) -> ModelType | None:
        """Get a single record by ID, or None if not found.

        Parameters
        ----------
        id : UUID | str
            Record UUID or string representation.

        Returns
        -------
        ModelType | None
            The database model instance or None.
        """
        record_uuid = self._parse_uuid(id, "id")
        stmt = select(self._model).where(self._model.id == record_uuid)
        stmt = self._apply_filters(stmt)
        return self._db.execute(stmt).scalar_one_or_none()

    def get_for_update(self, id: uuid.UUID | str) -> ModelType:
        """Get a single record with row-level lock for updates.

        Uses SELECT FOR UPDATE to prevent race conditions when multiple
        requests try to modify the same record simultaneously.

        Parameters
        ----------
        id : UUID | str
            Record UUID or string representation.

        Returns
        -------
        ModelType
            The database model instance.

        Raises
        ------
        HTTPException
            404 if record not found or doesn't belong to tenant/workspace.
        """
        record_uuid = self._parse_uuid(id, "id")
        stmt = select(self._model).where(self._model.id == record_uuid)
        stmt = self._apply_filters(stmt)
        stmt = stmt.with_for_update()
        result = self._db.execute(stmt).scalar_one_or_none()
        if result is None:
            raise HTTPException(status_code=404, detail=f"{self._model_name} not found")
        return result

    def list(
        self,
        limit: int = 20,
        cursor: uuid.UUID | str | None = None,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> list[ModelType]:
        """List records with pagination and tenant/workspace filtering.

        Parameters
        ----------
        limit : int
            Maximum number of records to return.
        cursor : UUID | str | None
            Pagination cursor (record ID for keyset pagination).
        order_by : str
            Column name to order by.
        order_desc : bool
            Order descending if True.

        Returns
        -------
        list[ModelType]
            List of database model instances.
        """
        stmt = select(self._model)
        stmt = self._apply_filters(stmt)

        order_column = getattr(self._model, order_by, self._model.created_at)
        if order_desc:
            stmt = stmt.order_by(order_column.desc(), self._model.id.desc())
        else:
            stmt = stmt.order_by(order_column.asc(), self._model.id.asc())

        if cursor:
            cursor_uuid = self._parse_uuid(cursor, "cursor")
            cursor_stmt = select(self._model).where(self._model.id == cursor_uuid)
            cursor_stmt = self._apply_filters(cursor_stmt)
            cursor_row = self._db.execute(cursor_stmt).scalar_one_or_none()
            if cursor_row is not None:
                cursor_value = getattr(cursor_row, order_by, None)
                if cursor_value is not None:
                    if order_desc:
                        stmt = stmt.where(
                            or_(
                                order_column < cursor_value,
                                and_(order_column == cursor_value, self._model.id < cursor_uuid),
                            )
                        )
                    else:
                        stmt = stmt.where(
                            or_(
                                order_column > cursor_value,
                                and_(order_column == cursor_value, self._model.id > cursor_uuid),
                            )
                        )
                elif order_desc:
                    stmt = stmt.where(self._model.id < cursor_uuid)
                else:
                    stmt = stmt.where(self._model.id > cursor_uuid)

        stmt = stmt.limit(limit)
        return list(self._db.execute(stmt).scalars().all())

    def exists(self, id: uuid.UUID | str) -> bool:
        """Check if a record exists with tenant/workspace filtering.

        Parameters
        ----------
        id : UUID | str
            Record UUID or string representation.

        Returns
        -------
        bool
            True if record exists, False otherwise.
        """
        record_uuid = self._parse_uuid(id, "id")
        stmt = select(func.count()).select_from(self._model).where(self._model.id == record_uuid)
        stmt = self._apply_filters(stmt)
        count = self._db.execute(stmt).scalar()
        return count > 0

    def count(self) -> int:
        """Count records with tenant/workspace filtering.

        Returns
        -------
        int
            Number of matching records.
        """
        stmt = select(func.count()).select_from(self._model)
        stmt = self._apply_filters(stmt)
        return self._db.execute(stmt).scalar() or 0

    def _apply_filters(self, stmt):
        """Apply tenant and workspace filters to a statement."""
        if self._tenant_id is not None and hasattr(self._model, "tenant_id"):
            stmt = stmt.where(self._model.tenant_id == self._tenant_id)
        if self._workspace_id is not None and hasattr(self._model, "workspace_id"):
            stmt = stmt.where(self._model.workspace_id == self._workspace_id)
        return stmt

    @staticmethod
    def _parse_uuid(value: uuid.UUID | str, label: str) -> uuid.UUID:
        """Parse and validate a UUID value.

        Parameters
        ----------
        value : UUID | str
            UUID or string to parse.
        label : str
            Label for error message.

        Returns
        -------
        UUID
            Parsed UUID.

        Raises
        ------
        HTTPException
            400 if value is not a valid UUID.
        """
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


def tenant_query(db: Session, model: Type[ModelType]) -> TenantQuery[ModelType]:
    """Factory function to create a TenantQuery instance.

    Parameters
    ----------
    db : Session
        SQLAlchemy session.
    model : Type[ModelType]
        Database model class.

    Returns
    -------
    TenantQuery[ModelType]
        Query builder instance.
    """
    return TenantQuery(db, model)


__all__ = ["TenantQuery", "tenant_query"]
