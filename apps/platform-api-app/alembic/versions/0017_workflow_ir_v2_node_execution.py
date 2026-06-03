"""add workflow ir v2 run metadata and node executions

Revision ID: 0017_workflow_ir_v2
Revises: 0016_rls_system_actor
Create Date: 2026-05-20

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0017_workflow_ir_v2"
down_revision = "0016_rls_system_actor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.add_column(sa.Column("workflow_spec_id", postgresql.UUID(as_uuid=True), nullable=True))
        batch_op.add_column(sa.Column("workflow_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("trigger_type", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("input_artifact_ids_json", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_workflow_runs_workflow_spec_id",
            "workflow_specs",
            ["workflow_spec_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.add_column(sa.Column("produced_by_node_id", sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column("parent_artifact_ids_json", sa.Text(), nullable=True))

    op.create_table(
        "workflow_node_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=150), nullable=False),
        sa.Column("node_type", sa.String(length=120), nullable=False),
        sa.Column("execution_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("inputs_json", sa.Text(), nullable=True),
        sa.Column("outputs_json", sa.Text(), nullable=True),
        sa.Column("logs_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("produced_artifact_ids_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id", "tenant_id"], ["workspaces.id", "workspaces.tenant_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("workflow_run_id", "node_id", name="uq_workflow_node_executions_run_node"),
    )
    op.create_index("ix_workflow_node_executions_run_status", "workflow_node_executions", ["workflow_run_id", "status"])
    op.create_index("ix_workflow_node_executions_workspace_created", "workflow_node_executions", ["workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_node_executions_workspace_created", table_name="workflow_node_executions")
    op.drop_index("ix_workflow_node_executions_run_status", table_name="workflow_node_executions")
    op.drop_table("workflow_node_executions")
    with op.batch_alter_table("artifacts") as batch_op:
        batch_op.drop_column("parent_artifact_ids_json")
        batch_op.drop_column("produced_by_node_id")
    with op.batch_alter_table("workflow_runs") as batch_op:
        batch_op.drop_constraint("fk_workflow_runs_workflow_spec_id", type_="foreignkey")
        batch_op.drop_column("input_artifact_ids_json")
        batch_op.drop_column("trigger_type")
        batch_op.drop_column("workflow_version")
        batch_op.drop_column("workflow_spec_id")
