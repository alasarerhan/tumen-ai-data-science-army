"""Enable Row Level Security for tenant isolation

Revision ID: 0008_rls
Revises: 0007_tenant_quota_events
Create Date: 2026-03-30

This migration implements PostgreSQL Row Level Security (RLS) for defense-in-depth
tenant isolation. Even if application code forgets a tenant_id filter, the database
will enforce isolation.

Best Practice Reference:
- https://www.techbuddies.io/2026/01/01/how-to-implement-postgresql-row-level-security-for-multi-tenant-saas/
- https://agnitestudio.com/blog/preventing-cross-tenant-leakage/

The application must set app.current_tenant_id at the start of each request:
    SET app.current_tenant_id = 'tenant-uuid-here';

Then all queries to RLS-protected tables will automatically filter by that tenant.

SECURITY NOTE: Table names are validated and quoted to prevent SQL injection.
"""

from __future__ import annotations

import re

from alembic import op

revision = "0008_rls"
down_revision = "0007_tenant_quota_events"
branch_labels = None
depends_on = None


def _quote_identifier(identifier: str) -> str:
    """Safely quote a SQL identifier to prevent injection.

    Validates that the identifier contains only safe characters
    and wraps it in double quotes for PostgreSQL.
    """
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
    "chat_sessions",
    "chat_uploads",
    "workflow_signal_events",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    op.execute("CREATE SCHEMA IF NOT EXISTS app")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid AS $$
            BEGIN
                RETURN current_setting('app.current_tenant_id', true)::uuid;
            END;
        $$ LANGUAGE plpgsql STABLE;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.set_tenant_context(p_tenant_id uuid) RETURNS void AS $$
            BEGIN
                EXECUTE format('SET app.current_tenant_id = %L', p_tenant_id::text);
            END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION app.reset_tenant_context() RETURNS void AS $$
            BEGIN
                RESET app.current_tenant_id;
            END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table in TENANT_SCOPED_TABLES:
        quoted_table = _quote_identifier(table)
        op.execute(f"ALTER TABLE {quoted_table} ENABLE ROW LEVEL SECURITY")

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
        ALTER TABLE workspace_memberships ENABLE ROW LEVEL SECURITY;

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
        ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

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
        ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

        CREATE POLICY chat_messages_tenant_policy ON chat_messages
            FOR ALL
            USING (
                EXISTS (
                    SELECT 1 FROM chat_sessions
                    WHERE chat_sessions.id = chat_messages.session_id
                    AND chat_sessions.tenant_id = app.current_tenant_id()
                )
                OR app.current_tenant_id() IS NULL
            );
        """
    )

    for table in TENANT_SCOPED_TABLES:
        quoted_table = _quote_identifier(table)
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {quoted_table} (tenant_id)")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workspace_memberships_workspace_id ON workspace_memberships (workspace_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_sessions_tenant_workspace ON chat_sessions (tenant_id, workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_runs_tenant_workspace ON workflow_runs (tenant_id, workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_artifacts_tenant_workspace ON artifacts (tenant_id, workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_specs_tenant_workspace ON workflow_specs (tenant_id, workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_uploads_tenant_workspace ON chat_uploads (tenant_id, workspace_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_workflow_signal_events_tenant_workspace ON workflow_signal_events (tenant_id, workspace_id)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    for table in TENANT_SCOPED_TABLES:
        quoted_table = _quote_identifier(table)
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {quoted_table}")
        op.execute(f"ALTER TABLE {quoted_table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS workspace_memberships_tenant_policy ON workspace_memberships")
    op.execute("ALTER TABLE workspace_memberships DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS audit_logs_tenant_policy ON audit_logs")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS chat_messages_tenant_policy ON chat_messages")
    op.execute("ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS app.current_tenant_id()")
    op.execute("DROP FUNCTION IF EXISTS app.set_tenant_context(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app.reset_tenant_context()")
    op.execute("DROP SCHEMA IF EXISTS app CASCADE")
