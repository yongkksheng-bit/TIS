"""Add is_deleted soft-delete flag to projects table.

Revision ID: w011_add_soft_delete
Revises: w010_add_plan_codes
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = "w011"
down_revision = "w010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    # Backfill: any existing projects are active (not deleted)
    op.execute("UPDATE projects SET is_deleted = false WHERE is_deleted IS NULL")


def downgrade() -> None:
    # NOTE: Physical deletion of user data is irreversible.
    # This drops the is_deleted column entirely.
    op.drop_column("projects", "is_deleted")
