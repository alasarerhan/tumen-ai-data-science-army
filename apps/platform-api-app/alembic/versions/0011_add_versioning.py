"""Add workflow versioning and canary deployment tables.

Revision ID: 0011_add_versioning
Revises: 0010_add_dlq_and_scheduler
Create Date: 2026-03-31

Adds:
- workflow_versions: Version history for workflow specifications
- canary_deployments: Canary deployment tracking with staged rollout
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_add_versioning"
down_revision = "0010_add_dlq_and_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("spec", postgresql.JSON, nullable=False),
        sa.Column("changelog", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
    )
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])
    op.create_index(
        "uq_workflow_versions_workflow_version",
        "workflow_versions",
        ["workflow_id", "version"],
        unique=True,
    )

    op.create_table(
        "canary_deployments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("workflow_id", sa.String(36), nullable=False),
        sa.Column("current_stage", sa.Integer, default=0, nullable=False),
        sa.Column("current_traffic", sa.Float, default=0.05, nullable=False),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("stages", postgresql.JSON, nullable=False),
        sa.Column("rollback_triggers", postgresql.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_reason", sa.Text, nullable=True),
    )
    op.create_index("ix_canary_deployments_version_id", "canary_deployments", ["version_id"])
    op.create_index("ix_canary_deployments_workflow_id", "canary_deployments", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_canary_deployments_workflow_id", table_name="canary_deployments")
    op.drop_index("ix_canary_deployments_version_id", table_name="canary_deployments")
    op.drop_table("canary_deployments")

    op.drop_index("uq_workflow_versions_workflow_version", table_name="workflow_versions")
    op.drop_index("ix_workflow_versions_workflow_id", table_name="workflow_versions")
    op.drop_table("workflow_versions")
