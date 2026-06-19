"""add production modelops store

Revision ID: 0021_modelops_production_store
Revises: 0020_agent_trace_metadata
Create Date: 2026-06-09

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0021_modelops_production_store"
down_revision = "0020_agent_trace_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_registry_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False, server_default="candidate"),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_state", sa.String(length=50), nullable=False, server_default="not_reviewed"),
        sa.Column("deployment_state", sa.String(length=50), nullable=False, server_default="not_deployed"),
        sa.Column("monitoring_status", sa.String(length=50), nullable=False, server_default="not_configured"),
        sa.Column("drift_status", sa.String(length=50), nullable=False, server_default="unknown"),
        sa.Column("performance_status", sa.String(length=50), nullable=False, server_default="unknown"),
        sa.Column("model_card_json", sa.Text(), nullable=True),
        sa.Column("rollback_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id", "tenant_id"], ["workspaces.id", "workspaces.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rollback_artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("workspace_id", "model_name", "version", name="uq_model_registry_workspace_name_version"),
    )
    op.create_index(
        "ix_model_registry_workspace_stage_created",
        "model_registry_entries",
        ["workspace_id", "stage", "created_at"],
    )

    op.create_table(
        "model_monitor_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("monitor_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="unknown"),
        sa.Column("metric_name", sa.String(length=120), nullable=True),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("threshold_value", sa.Float(), nullable=True),
        sa.Column("baseline_json", sa.Text(), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("remediation_workflow", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id", "tenant_id"], ["workspaces.id", "workspaces.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_model_monitor_workspace_created", "model_monitor_snapshots", ["workspace_id", "created_at"])
    op.create_index("ix_model_monitor_model_status", "model_monitor_snapshots", ["model_id", "status"])

    op.create_table(
        "model_deployment_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="planned"),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rollback_notes", sa.Text(), nullable=True),
        sa.Column("health_status", sa.String(length=50), nullable=False, server_default="unknown"),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id", "tenant_id"], ["workspaces.id", "workspaces.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["model_id"], ["model_registry_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rollback_model_id"], ["model_registry_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_model_deployments_workspace_env_status",
        "model_deployment_records",
        ["workspace_id", "environment", "status"],
    )
    op.create_index("ix_model_deployments_model_created", "model_deployment_records", ["model_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_model_deployments_model_created", table_name="model_deployment_records")
    op.drop_index("ix_model_deployments_workspace_env_status", table_name="model_deployment_records")
    op.drop_table("model_deployment_records")
    op.drop_index("ix_model_monitor_model_status", table_name="model_monitor_snapshots")
    op.drop_index("ix_model_monitor_workspace_created", table_name="model_monitor_snapshots")
    op.drop_table("model_monitor_snapshots")
    op.drop_index("ix_model_registry_workspace_stage_created", table_name="model_registry_entries")
    op.drop_table("model_registry_entries")
