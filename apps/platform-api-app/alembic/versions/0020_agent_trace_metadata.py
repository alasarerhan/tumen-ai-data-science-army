"""add agent trace metadata fields

Revision ID: 0020_agent_trace_metadata
Revises: 0019_agent_execution_traces
Create Date: 2026-06-04

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_agent_trace_metadata"
down_revision = "0019_agent_execution_traces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_execution_traces", sa.Column("token_usage_json", sa.Text(), nullable=True))
    op.add_column(
        "agent_execution_traces", sa.Column("cost_summary_json", sa.Text(), nullable=True)
    )
    op.add_column(
        "agent_execution_traces", sa.Column("evaluation_summary_json", sa.Text(), nullable=True)
    )
    op.add_column(
        "agent_execution_traces", sa.Column("version_metadata_json", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("agent_execution_traces", "version_metadata_json")
    op.drop_column("agent_execution_traces", "evaluation_summary_json")
    op.drop_column("agent_execution_traces", "cost_summary_json")
    op.drop_column("agent_execution_traces", "token_usage_json")
