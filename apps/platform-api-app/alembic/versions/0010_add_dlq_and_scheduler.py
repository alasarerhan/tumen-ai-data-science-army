"""Add DLQ and scheduled jobs tables.

Revision ID: 0010_add_dlq_and_scheduler
Revises: 0009_artifact_expires
Create Date: 2026-03-30

Adds:
- outbox_dlq: Dead Letter Queue for failed outbox events
- scheduled_jobs: Background job scheduling with leader election
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010_add_dlq_and_scheduler"
down_revision = "0009_artifact_expires"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_dlq",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("original_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(150), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("final_error", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False),
        sa.Column("original_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "moved_to_dlq_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column("reviewed", sa.Boolean, default=False, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
    )
    op.create_index("ix_outbox_dlq_created_at", "outbox_dlq", ["created_at"])
    op.create_index("ix_outbox_dlq_event_type", "outbox_dlq", ["event_type"])

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("interval_seconds", sa.Integer, nullable=True),
        sa.Column("enabled", sa.Boolean, default=True, nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(50), nullable=True),
        sa.Column("last_run_error", sa.Text, nullable=True),
        sa.Column("leader_id", sa.String(100), nullable=True),
        sa.Column("leader_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            onupdate=sa.func.current_timestamp(),
            nullable=False,
        ),
    )
    op.create_index("ix_scheduled_jobs_next_run", "scheduled_jobs", ["next_run_at"])
    op.create_index("uq_scheduled_jobs_name", "scheduled_jobs", ["job_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_scheduled_jobs_next_run", table_name="scheduled_jobs")
    op.drop_index("uq_scheduled_jobs_name", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")

    op.drop_index("ix_outbox_dlq_event_type", table_name="outbox_dlq")
    op.drop_index("ix_outbox_dlq_created_at", table_name="outbox_dlq")
    op.drop_table("outbox_dlq")
