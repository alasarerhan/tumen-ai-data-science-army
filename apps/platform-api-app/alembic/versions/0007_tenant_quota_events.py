"""add tenant quota events table

Revision ID: 0007_tenant_quota_events
Revises: 0006_chat_and_signals
Create Date: 2026-03-23

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0007_tenant_quota_events"
down_revision = "0006_chat_and_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_quota_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_tenant_quota_events_tenant_created",
        "tenant_quota_events",
        ["tenant_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_quota_events_tenant_created", table_name="tenant_quota_events")
    op.drop_table("tenant_quota_events")
