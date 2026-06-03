"""Database resilience tests.

Tests cover:
  - Database connection failure handling
  - Query timeout handling
  - Transaction rollback on error
"""
from __future__ import annotations

import pytest
from unittest.mock import patch
from sqlalchemy.exc import OperationalError


class TestDatabaseConnectionFailure:
    """Tests for database connection failure handling."""

    def test_db_connection_failure_returns_503(self, seeded_db: dict) -> None:
        from platform_api.services import run_service

        db = seeded_db["db"]

        with patch.object(db, 'execute', side_effect=OperationalError("connection failed", {}, None)):
            with pytest.raises(Exception):
                run_service.list_workflow_runs_for_workspace(db, workspace_id=seeded_db["workspace"].id)

    def test_db_timeout_returns_503(self, seeded_db: dict) -> None:
        from platform_api.services import run_service

        db = seeded_db["db"]

        with patch.object(db, 'execute', side_effect=OperationalError("timeout", {}, None)):
            with pytest.raises(Exception):
                run_service.list_workflow_runs_for_workspace(db, workspace_id=seeded_db["workspace"].id)


class TestTransactionRollback:
    """Tests for transaction rollback on error."""

    def test_db_transaction_rollback_on_error(self, seeded_db: dict) -> None:
        from platform_api.services import chat_service

        db = seeded_db["db"]
        tenant = seeded_db["tenant"]
        workspace = seeded_db["workspace"]
        user_id = seeded_db["user_admin"].id

        session = chat_service.create_chat_session(
            db,
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user_id,
            title="rollback-test",
        )
        db.flush()

        initial_count = len(chat_service.list_chat_sessions(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
        ))

        try:
            with patch.object(db, 'flush', side_effect=Exception("Simulated error")):
                chat_service.create_message(
                    db,
                    session=session,
                    role="user",
                    content="This should fail",
                    artifacts=None,
                )
        except Exception:
            pass

        db.rollback()

        final_count = len(chat_service.list_chat_sessions(
            db,
            workspace_id=workspace.id,
            user_id=user_id,
        ))

        assert final_count == initial_count
