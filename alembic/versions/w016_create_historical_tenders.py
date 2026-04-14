"""w016: Create historical_tenders table.

Revision ID: w016
Revises: w015
Create Date: 2026-04-13

Hard-isolated tender archive: completed tenders used for
RAG enrichment and pricing benchmark analytics.
Does NOT appear in the active Project list.

The 'winning_price' column is the golden signal — the only
reliable competitive intelligence point in our asymmetric data landscape.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = 'w016'
down_revision = 'w015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'historical_tenders',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('project_name', sa.String(length=500), nullable=False),
        sa.Column('owner_unit', sa.String(length=500), nullable=True),
        sa.Column('region', sa.String(length=100), nullable=True),
        sa.Column('province', sa.String(length=50), nullable=True),
        sa.Column('project_type', sa.String(length=20), nullable=True),
        sa.Column('budget_amount', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='CNY'),
        sa.Column('winning_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('winning_price_usd', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('price_revealed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('bid_open_date', sa.Date(), nullable=True),
        sa.Column('submission_deadline', sa.DateTime(), nullable=True),
        sa.Column('estimated_duration_months', sa.BigInteger(), nullable=True),
        sa.Column('plan_code', sa.String(length=100), nullable=True),
        sa.Column('agency_project_code', sa.String(length=100), nullable=True),
        sa.Column('winning_bidder', sa.String(length=500), nullable=True),
        sa.Column('tender_status', sa.String(length=20), nullable=False, server_default='closed'),
        sa.Column('tender_file_path', sa.String(length=1000), nullable=True),
        sa.Column('tender_file_hash', sa.String(length=64), nullable=True),
        sa.Column('scoring_criteria_json', JSON(), nullable=True),
        sa.Column('metadata_json', JSON(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=True),
        sa.Column('imported_by', sa.BigInteger(), nullable=True),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
    )
    op.create_index('ix_ht_region', 'historical_tenders', ['region'])
    op.create_index('ix_ht_province', 'historical_tenders', ['province'])
    op.create_index('ix_ht_project_type', 'historical_tenders', ['project_type'])
    op.create_index('ix_ht_tender_status', 'historical_tenders', ['tender_status'])
    op.create_index('ix_ht_tender_file_hash', 'historical_tenders', ['tender_file_hash'])
    op.create_index('ix_ht_winning_price', 'historical_tenders', ['winning_price'])
    op.create_index('ix_ht_budget_amount', 'historical_tenders', ['budget_amount'])


def downgrade() -> None:
    op.drop_table('historical_tenders')
