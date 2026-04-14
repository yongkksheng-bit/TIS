"""w017: Create historical_bids table.

Revision ID: w017
Revises: w016
Create Date: 2026-04-13

Our company's historical bid records — one row per (tender × bid) combination.
Records our price, outcome, and competitive position.

Key derived field: price_gap_percentage
  = (our_bid_price - winning_price) / winning_price × 100
  Positive = we overpriced; negative = we underpriced (possible win);
  ~0 = we priced at market.

foreign key: historical_tender_id → historical_tenders.id (ON DELETE CASCADE)
"""
from alembic import op
import sqlalchemy as sa


revision = 'w017'
down_revision = 'w016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'historical_bids',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('historical_tender_id', sa.BigInteger(), nullable=False),
        sa.Column('our_bid_price', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('our_bid_submission_date', sa.Date(), nullable=True),
        sa.Column('our_bid_status', sa.String(length=20), nullable=True),
        sa.Column('price_gap_percentage', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('price_gap_bucket', sa.String(length=30), nullable=True),
        sa.Column('win_rank', sa.BigInteger(), nullable=True),
        sa.Column('total_bidders_count', sa.BigInteger(), nullable=True),
        sa.Column('is_sole_bidder', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('internal_postmortem_id', sa.BigInteger(), nullable=True),
        sa.Column('bid_file_path', sa.String(length=1000), nullable=True),
        sa.Column('is_postmortem_completed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        # FK 引用 historical_tenders
        sa.ForeignKeyConstraint(
            ['historical_tender_id'],
            ['historical_tenders.id'],
            ondelete='CASCADE',
            name='fk_hb_tender'
        ),
    )
    op.create_index('ix_hb_tender_id', 'historical_bids', ['historical_tender_id'])
    op.create_index('ix_hb_status', 'historical_bids', ['our_bid_status'])
    op.create_index('ix_hb_price_gap_bucket', 'historical_bids', ['price_gap_bucket'])
    op.create_index('ix_hb_price_gap_pct', 'historical_bids', ['price_gap_percentage'])


def downgrade() -> None:
    op.drop_table('historical_bids')
