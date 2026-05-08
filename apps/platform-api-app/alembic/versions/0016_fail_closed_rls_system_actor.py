"""Make tenant RLS fail closed and allow only explicit system actors.

Revision ID: 0016_rls_system_actor
Revises: 0015_outbox_tenant_scope
Create Date: 2026-04-13
"""

from __future__ import annotations

import re

from alembic import op

revision = "0016_rls_system_actor"
down_revision = "0015_outbox_tenant_scope"
branch_labels = None
depends_on = None


def _quote_identifier(identifier: str) -> str:
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise ValueError(f"Invalid SQL identifier: {identifier}")
    return f'"{identifier}"'


TENANT_SCOPED_TABLES = [
    "workspaces",
    "tenant_memberships",
    "invites",
    "workflow_runs",
    "tenant_quota_events",
    "artifacts",
    "workflow_specs",
    "data_sources",
    "hitl_approvals",
    "chat_sessions",
    "chat_uploads",
    "workflow_signal_events",
    "outbox_events",
    "outbox_dlq",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    op.execute("CREATE SCHEMA IF NOT EXISTS app")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_actor_is_system() RETURNS boolean AS $$
            DECLARE
                raw_setting text;
            BEGIN
                raw_setting := current_setting('app.current_actor_is_system', true);
                IF raw_setting IS NULL OR raw_setting = '' THEN
                    RETURN false;
                END IF;
                RETURN raw_setting::boolean;
            EXCEPTION
                WHEN OTHERS THEN
                    RETURN false;
            END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    for table in TENANT_SCOPED_TABLES:
        quoted_table = _quote_identifier(table)
        op.execute(f"ALTER TABLE {quoted_table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted_table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {quoted_table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON {quoted_table}
                FOR ALL
                USING (
                    app.current_actor_is_system()
                    OR tenant_id = app.current_tenant_id()
                )
                WITH CHECK (
                    app.current_actor_is_system()
                    OR tenant_id = app.current_tenant_id()
                )
            """
        )

    op.execute(
        """
        ALTER TABLE workspace_memberships ENABLE ROW LEVEL SECURITY;
        ALTER TABLE workspace_memberships FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS workspace_memberships_tenant_policy ON workspace_memberships;

        CREATE POLICY workspace_memberships_tenant_policy ON workspace_memberships
            FOR ALL
            USING (
                app.current_actor_is_system()
                OR EXISTS (
                    SELECT 1 FROM workspaces
                    WHERE workspaces.id = workspace_memberships.workspace_id
                    AND workspaces.tenant_id = app.current_tenant_id()
                )
            )
            WITH CHECK (
                app.current_actor_is_system()
                OR EXISTS (
                    SELECT 1 FROM workspaces
                    WHERE workspaces.id = workspace_memberships.workspace_id
                    AND workspaces.tenant_id = app.current_tenant_id()
                )
            );
        """
    )

    op.execute(
        """
        ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS audit_logs_tenant_policy ON audit_logs;

        CREATE POLICY audit_logs_tenant_policy ON audit_logs
            FOR SELECT
            USING (
                app.current_actor_is_system()
                OR tenant_id = app.current_tenant_id()
            );
        """
    )

    op.execute(
        """
        ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
        ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS chat_messages_tenant_policy ON chat_messages;

        CREATE POLICY chat_messages_tenant_policy ON chat_messages
            FOR ALL
            USING (
                app.current_actor_is_system()
                OR EXISTS (
                    SELECT 1 FROM chat_sessions
                    WHERE chat_sessions.id = chat_messages.session_id
                    AND chat_sessions.tenant_id = app.current_tenant_id()
                )
            )
            WITH CHECK (
                app.current_actor_is_system()
                OR EXISTS (
                    SELECT 1 FROM chat_sessions
                    WHERE chat_sessions.id = chat_messages.session_id
                    AND chat_sessions.tenant_id = app.current_tenant_id()
                )
            );
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    for table in TENANT_SCOPED_TABLES:
        quoted_table = _quote_identifier(table)
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {quoted_table}")
        op.execute(f"ALTER TABLE {quoted_table} NO FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON {quoted_table}
                FOR ALL
                USING (
                    tenant_id = app.current_tenant_id()
                    OR app.current_tenant_id() IS NULL
                )
                WITH CHECK (
                    tenant_id = app.current_tenant_id()
                    OR app.current_tenant_id() IS NULL
                )
            """
        )

    op.execute(
        """
        DROP POLICY IF EXISTS workspace_memberships_tenant_policy ON workspace_memberships;
        ALTER TABLE workspace_memberships NO FORCE ROW LEVEL SECURITY;

        CREATE POLICY workspace_memberships_tenant_policy ON workspace_memberships
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM workspaces
                    WHERE workspaces.id = workspace_memberships.workspace_id
                    AND workspaces.tenant_id = app.current_tenant_id()
                )
                OR app.current_tenant_id() IS NULL
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM workspaces
                    WHERE workspaces.id = workspace_memberships.workspace_id
                    AND workspaces.tenant_id = app.current_tenant_id()
                )
                OR app.current_tenant_id() IS NULL
            );
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS audit_logs_tenant_policy ON audit_logs;
        ALTER TABLE audit_logs NO FORCE ROW LEVEL SECURITY;

        CREATE POLICY audit_logs_tenant_policy ON audit_logs
            FOR SELECT
            USING (
                tenant_id = app.current_tenant_id()
                OR app.current_tenant_id() IS NULL
            );
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS chat_messages_tenant_policy ON chat_messages;
        ALTER TABLE chat_messages NO FORCE ROW LEVEL SECURITY;

        CREATE POLICY chat_messages_tenant_policy ON chat_messages
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM chat_sessions
                    WHERE chat_sessions.id = chat_messages.session_id
                    AND chat_sessions.tenant_id = app.current_tenant_id()
                )
                OR app.current_tenant_id() IS NULL
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM chat_sessions
                    WHERE chat_sessions.id = chat_messages.session_id
                    AND chat_sessions.tenant_id = app.current_tenant_id()
                )
                OR app.current_tenant_id() IS NULL
            );
        """
    )

    op.execute("DROP FUNCTION IF EXISTS app.current_actor_is_system()")
