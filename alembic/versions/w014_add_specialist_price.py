"""w014: Add specialist_price to pricing_decisions for dual-track pricing.

Revision ID: w014
Revises: w013
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa


revision = 'w014'
down_revision = 'w013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('pricing_decisions', 'boss_final_price', existing_type=sa.Numeric(15, 2), nullable=True)
    op.add_column('pricing_decisions', sa.Column('specialist_price', sa.Numeric(15, 2), nullable=True))
    op.add_column('pricing_decisions', sa.Column('specialist_notes', sa.Text(), nullable=True))
    op.add_column('pricing_decisions', sa.Column('action_type', sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column('pricing_decisions', 'action_type')
    op.drop_column('pricing_decisions', 'specialist_notes')
    op.drop_column('pricing_decisions', 'specialist_price')
    op.alter_column('pricing_decisions', 'boss_final_price', existing_type=sa.Numeric(15, 2), nullable=False)
