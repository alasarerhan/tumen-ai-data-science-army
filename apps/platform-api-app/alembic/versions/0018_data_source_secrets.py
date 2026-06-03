"""add durable data source secret storage

Revision ID: 0018_data_source_secrets
Revises: 0017_workflow_ir_v2
Create Date: 2026-06-03

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0018_data_source_secrets"
down_revision = "0017_workflow_ir_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_source_secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id", "tenant_id"], ["workspaces.id", "workspaces.tenant_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_data_source_secrets_workspace_created",
        "data_source_secrets",
        ["workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_data_source_secrets_workspace_created", table_name="data_source_secrets")
    op.drop_table("data_source_secrets")
