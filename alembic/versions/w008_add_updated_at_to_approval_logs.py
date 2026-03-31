"""Add missing updated_at column to approval_logs

Revision ID: w008
Revises: w007
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'w008'
down_revision = 'w007'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('approval_logs',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True))


def downgrade() -> None:
    op.drop_column('approval_logs', 'updated_at')
