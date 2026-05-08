"""Enforce unique normalized email per user account.

Revision ID: 0012_unique_user_email
Revises: 0011_add_versioning
Create Date: 2026-04-13
"""

from __future__ import annotations

from alembic import op

revision = "0012_unique_user_email"
down_revision = "0011_add_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("uq_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_users_email", table_name="users")
