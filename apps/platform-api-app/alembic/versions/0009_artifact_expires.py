"""add artifact expires_at for cleanup policy

Revision ID: 0009_artifact_expires
Revises: 0008_tenant_rls
Create Date: 2026-03-30

FinOps: Adds TTL column for artifact cleanup to prevent unbounded storage growth.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0009_artifact_expires"
down_revision = "0008_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_artifacts_expires_at",
        "artifacts",
        ["expires_at"],
    )
    op.create_index(
        "ix_workflow_runs_status_created",
        "workflow_runs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_artifacts_workspace_created",
        "artifacts",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifacts_workspace_created", table_name="artifacts")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_workflow_runs_status_created", table_name="workflow_runs")
    op.drop_index("ix_artifacts_expires_at", table_name="artifacts")
    op.drop_column("artifacts", "expires_at")
