"""add agent execution trace storage

Revision ID: 0019_agent_execution_traces
Revises: 0018_data_source_secrets
Create Date: 2026-06-04

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0019_agent_execution_traces"
down_revision = "0018_data_source_secrets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_execution_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_node_execution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=150), nullable=False),
        sa.Column("node_type", sa.String(length=120), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("executor_kind", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="running"),
        sa.Column("input_summary_json", sa.Text(), nullable=True),
        sa.Column("output_summary_json", sa.Text(), nullable=True),
        sa.Column("tool_calls_json", sa.Text(), nullable=True),
        sa.Column("artifact_ids_json", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["workflow_node_execution_id"], ["workflow_node_executions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "tenant_id"],
            ["workspaces.id", "workspaces.tenant_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_agent_execution_traces_node_created",
        "agent_execution_traces",
        ["workflow_node_execution_id", "created_at"],
    )
    op.create_index(
        "ix_agent_execution_traces_workspace_created",
        "agent_execution_traces",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "ix_agent_execution_traces_run_status",
        "agent_execution_traces",
        ["workflow_run_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_execution_traces_run_status", table_name="agent_execution_traces")
    op.drop_index(
        "ix_agent_execution_traces_workspace_created", table_name="agent_execution_traces"
    )
    op.drop_index("ix_agent_execution_traces_node_created", table_name="agent_execution_traces")
    op.drop_table("agent_execution_traces")
