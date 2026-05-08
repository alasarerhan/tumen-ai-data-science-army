"""Fix canary deployment relationship to workflow versions.

Revision ID: 0013_fix_canary_version_fk
Revises: 0012_unique_user_email
Create Date: 2026-04-13
"""

from __future__ import annotations

from alembic import op

revision = "0013_fix_canary_version_fk"
down_revision = "0012_unique_user_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind is not None and bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_canary_deployments_version_id",
            "canary_deployments",
            "workflow_versions",
            ["version_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(
        "uq_canary_deployments_version_id",
        "canary_deployments",
        ["version_id"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("uq_canary_deployments_version_id", table_name="canary_deployments")
    if bind is not None and bind.dialect.name != "sqlite":
        op.drop_constraint("fk_canary_deployments_version_id", "canary_deployments", type_="foreignkey")
