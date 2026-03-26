"""Add Week 4 pricing tables: cost_estimates, pricing_decisions, price_history"""
from alembic import op
import sqlalchemy as sa

revision = 'w004'
down_revision = 'w003'
branch_labels = None
depends_on = None


def upgrade():
    # cost_estimates (version-controlled cost breakdown)
    op.create_table(
        'cost_estimates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, default=1),
        sa.Column('food_cost', sa.Numeric(15, 2), nullable=False),
        sa.Column('logistics_cost', sa.Numeric(15, 2), nullable=False),
        sa.Column('labor_cost', sa.Numeric(15, 2), nullable=False),
        sa.Column('management_cost', sa.Numeric(15, 2), nullable=False),
        sa.Column('other_cost', sa.Numeric(15, 2), nullable=False, default=0),
        sa.Column('total_cost', sa.Numeric(15, 2), nullable=False),
        sa.Column('estimated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('estimate_reason', sa.Text(), nullable=True),
        sa.Column('is_confirmed', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.UniqueConstraint('project_id', 'version_number', name='uq_cost_est_project_version'),
    )

    # pricing_decisions (three-level pricing decision records)
    op.create_table(
        'pricing_decisions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cost_estimate_id', sa.Integer(),
                  sa.ForeignKey('cost_estimates.id'), nullable=True),
        sa.Column('cost_base', sa.Numeric(15, 2), nullable=False),
        sa.Column('system_suggested_low', sa.Numeric(15, 2), nullable=False),
        sa.Column('system_suggested_high', sa.Numeric(15, 2), nullable=False),
        sa.Column('system_suggested_optimal', sa.Numeric(15, 2), nullable=True),
        sa.Column('finance_suggested_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('finance_suggestion_reason', sa.Text(), nullable=True),
        sa.Column('boss_final_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('boss_decision_reason', sa.Text(), nullable=True),
        sa.Column('deviation_from_system', sa.Numeric(5, 4), nullable=True),
        sa.Column('deviation_reason_category', sa.String(50), nullable=True),
        sa.Column('budget_limit', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_under_limit', sa.Boolean(), nullable=True),
        sa.Column('limit_violation_warning', sa.Text(), nullable=True),
        sa.Column('game_theory_analysis', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), default='decided', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    # price_history (historical bid data for cold-start)
    op.create_table(
        'price_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_type', sa.String(100), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('budget_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('our_cost', sa.Numeric(15, 2), nullable=True),
        sa.Column('our_bid_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('winning_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('winning_unit', sa.String(255), nullable=True),
        sa.Column('discount_rate', sa.Numeric(5, 4), nullable=True),
        sa.Column('bid_date', sa.Date(), nullable=True),
        sa.Column('is_our_win', sa.Boolean(), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )


def downgrade():
    op.drop_table('price_history')
    op.drop_table('pricing_decisions')
    op.drop_table('cost_estimates')
