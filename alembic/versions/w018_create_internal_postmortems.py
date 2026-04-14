"""w018: Create internal_postmortems table.

Revision ID: w018
Revises: w017
Create Date: 2026-04-13

Structured lessons learned from historical bid outcomes.
Expert feedback text is chunked and stored in knowledge_chunks
with win_signal tags to enable dual-track RAG retrieval.

Key design: expert_feedback_text is stored as plain TEXT
(not JSON) because it can be several pages long.
Structured tags (loss_root_cause_tags, win_breakthrough_tags) are
extracted via LLM prompting and stored as ARRAY(String).

foreign key: historical_bid_id → historical_bids.id (ON DELETE CASCADE)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


revision = 'w018'
down_revision = 'w017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'internal_postmortems',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('historical_bid_id', sa.BigInteger(), nullable=False),
        sa.Column('outcome', sa.String(length=20), nullable=True),
        sa.Column('key_win_factors', ARRAY(sa.String(length=100), dimensions=1), nullable=True),
        sa.Column('key_loss_factors', ARRAY(sa.String(length=100), dimensions=1), nullable=True),
        sa.Column('score_received', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('score_max', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('technical_score_received', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('price_score_received', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('loss_root_cause_tags', ARRAY(sa.String(length=50), dimensions=1), nullable=True),
        sa.Column('win_breakthrough_tags', ARRAY(sa.String(length=50), dimensions=1), nullable=True),
        sa.Column('expert_feedback_text', sa.Text(), nullable=True),
        sa.Column('confidential_level', sa.String(length=20), nullable=False, server_default='internal'),
        sa.Column('created_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        # FK 引用 historical_bids（延迟创建，避免循环）
        sa.ForeignKeyConstraint(
            ['historical_bid_id'],
            ['historical_bids.id'],
            ondelete='CASCADE',
            name='fk_ip_bid'
        ),
    )
    op.create_index('ix_ip_bid_id', 'internal_postmortems', ['historical_bid_id'])
    op.create_index('ix_ip_outcome', 'internal_postmortems', ['outcome'])
    op.create_index('ix_ip_confidential', 'internal_postmortems', ['confidential_level'])

    # 回填 historical_bids.internal_postmortem_id FK（w017时尚未创建此表）
    op.create_foreign_key(
        'fk_hb_postmortem_id',
        'historical_bids', 'internal_postmortems',
        ['internal_postmortem_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_hb_postmortem_id', 'historical_bids', type_='foreignkey')
    op.drop_table('internal_postmortems')
