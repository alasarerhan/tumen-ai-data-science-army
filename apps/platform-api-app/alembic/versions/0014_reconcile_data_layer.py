"""Reconcile data layer schema with application models.

Revision ID: 0014_reconcile_data_layer
Revises: 0013_fix_canary_version_fk
Create Date: 2026-04-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_reconcile_data_layer"
down_revision = "0013_fix_canary_version_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.create_unique_constraint("uq_workspaces_id_tenant", ["id", "tenant_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(150), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_events_status_created", "outbox_events", ["status", "created_at"])
    op.create_index("ix_outbox_events_aggregate", "outbox_events", ["aggregate_type", "aggregate_id"])
    op.create_index(
        "ix_outbox_events_status_retry_created",
        "outbox_events",
        ["status", "next_retry_at", "created_at"],
    )

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("connection_uri", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "tenant_id"],
            ["workspaces.id", "workspaces.tenant_id"],
            ondelete="CASCADE",
            name="fk_data_sources_workspace_tenant",
        ),
    )
    op.create_index("ix_data_sources_workspace_created", "data_sources", ["workspace_id", "created_at"])

    op.create_table(
        "hitl_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("step_key", sa.String(length=150), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "tenant_id"],
            ["workspaces.id", "workspaces.tenant_id"],
            ondelete="CASCADE",
            name="fk_hitl_approvals_workspace_tenant",
        ),
    )
    op.create_index(
        "ix_hitl_approvals_workspace_status_created",
        "hitl_approvals",
        ["workspace_id", "status", "created_at"],
    )

    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.create_foreign_key(
            "fk_workflow_runs_workspace_tenant",
            "workspaces",
            ["workspace_id", "tenant_id"],
            ["id", "tenant_id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.create_foreign_key(
            "fk_artifacts_workspace_tenant",
            "workspaces",
            ["workspace_id", "tenant_id"],
            ["id", "tenant_id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("workflow_specs") as batch_op:
        batch_op.create_foreign_key(
            "fk_workflow_specs_workspace_tenant",
            "workspaces",
            ["workspace_id", "tenant_id"],
            ["id", "tenant_id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.create_foreign_key(
            "fk_chat_sessions_workspace_tenant",
            "workspaces",
            ["workspace_id", "tenant_id"],
            ["id", "tenant_id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("chat_uploads") as batch_op:
        batch_op.create_foreign_key(
            "fk_chat_uploads_workspace_tenant",
            "workspaces",
            ["workspace_id", "tenant_id"],
            ["id", "tenant_id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("workflow_signal_events") as batch_op:
        batch_op.create_foreign_key(
            "fk_workflow_signal_events_workspace_tenant",
            "workspaces",
            ["workspace_id", "tenant_id"],
            ["id", "tenant_id"],
            ondelete="CASCADE",
        )
    op.create_index("ix_workflow_runs_workspace_created", "workflow_runs", ["workspace_id", "created_at"])

    op.create_index(
        "ix_invites_tenant_workspace_email_status",
        "invites",
        ["tenant_id", "workspace_id", "email", "status"],
    )
    op.create_index(
        "ix_chat_sessions_workspace_user_updated",
        "chat_sessions",
        ["workspace_id", "user_id", "updated_at"],
    )
    op.create_index("ix_workflow_specs_workspace_created", "workflow_specs", ["workspace_id", "created_at"])
    op.create_index("ix_chat_uploads_workspace_created", "chat_uploads", ["workspace_id", "created_at"])
    op.create_index(
        "ix_workflow_signal_events_run_created",
        "workflow_signal_events",
        ["workflow_run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_signal_events_run_created", table_name="workflow_signal_events")
    op.drop_index("ix_chat_uploads_workspace_created", table_name="chat_uploads")
    op.drop_index("ix_workflow_specs_workspace_created", table_name="workflow_specs")
    op.drop_index("ix_chat_sessions_workspace_user_updated", table_name="chat_sessions")
    op.drop_index("ix_invites_tenant_workspace_email_status", table_name="invites")
    op.drop_index("ix_workflow_runs_workspace_created", table_name="workflow_runs")

    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint("fk_workflow_runs_workspace_tenant", type_="foreignkey")
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.drop_constraint("fk_artifacts_workspace_tenant", type_="foreignkey")
    with op.batch_alter_table("workflow_specs") as batch_op:
        batch_op.drop_constraint("fk_workflow_specs_workspace_tenant", type_="foreignkey")
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_constraint("fk_chat_sessions_workspace_tenant", type_="foreignkey")
    with op.batch_alter_table("chat_uploads") as batch_op:
        batch_op.drop_constraint("fk_chat_uploads_workspace_tenant", type_="foreignkey")
    with op.batch_alter_table("workflow_signal_events") as batch_op:
        batch_op.drop_constraint("fk_workflow_signal_events_workspace_tenant", type_="foreignkey")

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_constraint("uq_workspaces_id_tenant", type_="unique")

    op.drop_index("ix_hitl_approvals_workspace_status_created", table_name="hitl_approvals")
    op.drop_table("hitl_approvals")

    op.drop_index("ix_data_sources_workspace_created", table_name="data_sources")
    op.drop_table("data_sources")

    op.drop_index("ix_outbox_events_status_retry_created", table_name="outbox_events")
    op.drop_index("ix_outbox_events_aggregate", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status_created", table_name="outbox_events")
    op.drop_table("outbox_events")
