"""Add index on is_deleted for query performance.

Revision ID: w012
Revises: w011
Create Date: 2026-03-31

All list queries and duplicate checks filter by is_deleted.
An index is required to avoid sequential scans as data grows.
"""
from alembic import op

revision = "w012"
down_revision = "w011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index: (is_deleted, status) covers the most common list queries
    op.create_index(
        "ix_projects_is_deleted_status",
        "projects",
        ["is_deleted", "status"],
    )
    # Index on is_deleted alone for simple duplicate-check lookups
    op.create_index(
        "ix_projects_is_deleted",
        "projects",
        ["is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_projects_is_deleted", "projects")
    op.drop_index("ix_projects_is_deleted_status", "projects")
