"""Add tenant scoping columns to outbox tables.

Revision ID: 0015_outbox_tenant_scope
Revises: 0014_reconcile_data_layer
Create Date: 2026-04-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_outbox_tenant_scope"
down_revision = "0014_reconcile_data_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_tenant_status_created",
        "outbox_events",
        ["tenant_id", "status", "created_at"],
    )

    op.add_column(
        "outbox_dlq",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "outbox_dlq",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_dlq_tenant_created",
        "outbox_dlq",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_dlq_tenant_created", table_name="outbox_dlq")
    op.drop_column("outbox_dlq", "workspace_id")
    op.drop_column("outbox_dlq", "tenant_id")

    op.drop_index("ix_outbox_events_tenant_status_created", table_name="outbox_events")
    op.drop_column("outbox_events", "workspace_id")
    op.drop_column("outbox_events", "tenant_id")
