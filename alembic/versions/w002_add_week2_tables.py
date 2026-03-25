"""Week 2 tables: owner_profiles, bid_evaluation_reports, approval_logs, discarded_projects

Revision ID: w002
Revises: w001
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = 'w002'
down_revision = 'w001'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add missing standard_cert_suggestion column to ocr_extractions
    op.add_column('ocr_extractions',
        sa.Column('standard_cert_suggestion', sa.Integer(),
                  sa.ForeignKey('standard_certifications.id', ondelete='SET NULL'),
                  nullable=True))

    # owner_profiles
    op.create_table('owner_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_name', sa.String(255), nullable=False),
        sa.Column('owner_type', sa.String(50), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('cooperation_count', sa.Integer(), default=0),
        sa.Column('last_cooperation_date', sa.Date(), nullable=True),
        sa.Column('relationship_level', sa.String(20), default='none'),
        sa.Column('avg_winning_discount', sa.Numeric(5, 2), nullable=True),
        sa.Column('preferred_styles', JSON, nullable=True),
        sa.Column('common_requirements', JSON, nullable=True),
        sa.Column('blacklist_flags', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('owner_name', 'region', name='uq_owner_name_region'),
    )

    # bid_evaluation_reports
    op.create_table('bid_evaluation_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_version', sa.Integer(), default=1),
        sa.Column('qualification_match_score', sa.Integer(), nullable=True),
        sa.Column('missing_mandatory_certs', JSON, nullable=True),
        sa.Column('missing_optional_certs', JSON, nullable=True),
        sa.Column('matched_certs_detail', JSON, nullable=True),
        sa.Column('days_until_bid_open', sa.Integer(), nullable=True),
        sa.Column('time_urgency_level', sa.String(20), nullable=True),
        sa.Column('is_time_sufficient', sa.Boolean(), nullable=True),
        sa.Column('owner_profile_id', sa.Integer(), sa.ForeignKey('owner_profiles.id'), nullable=True),
        sa.Column('relationship_index', sa.Integer(), nullable=True),
        sa.Column('is_new_owner', sa.Boolean(), nullable=True),
        sa.Column('estimated_cost', sa.Numeric(15, 2), nullable=True),
        sa.Column('suggested_price_range_low', sa.Numeric(15, 2), nullable=True),
        sa.Column('suggested_price_range_high', sa.Numeric(15, 2), nullable=True),
        sa.Column('cost_estimate_confidence', sa.String(20), nullable=True),
        sa.Column('overall_win_probability', sa.Numeric(5, 4), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('fatal_risks', JSON, nullable=True),
        sa.Column('warning_risks', JSON, nullable=True),
        sa.Column('recommendation', sa.String(20), nullable=True),
        sa.Column('recommendation_reason', sa.String(500), nullable=True),
        sa.Column('generated_by', sa.String(50), default='system'),
        sa.Column('confirmed_by_specialist', sa.Boolean(), default=False),
        sa.Column('specialist_decision', sa.String(20), nullable=True),
        sa.Column('specialist_notes', sa.String(500), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('overridden_by_boss', sa.Boolean(), default=False),
        sa.Column('boss_override_reason', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('project_id', 'report_version', name='uq_project_version'),
    )

    # approval_logs
    op.create_table('approval_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('actor_role', sa.String(50), nullable=False),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reason_text', sa.Text(), nullable=True),
        sa.Column('original_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # discarded_projects
    op.create_table('discarded_projects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('original_evaluation_report_id', sa.Integer(), sa.ForeignKey('bid_evaluation_reports.id'), nullable=True),
        sa.Column('discarded_by', sa.String(50), nullable=False),
        sa.Column('discard_reason', sa.Text(), nullable=True),
        sa.Column('discard_stage', sa.String(50), nullable=True),
        sa.Column('can_be_revived', sa.Boolean(), default=True),
        sa.Column('revived_at', sa.DateTime(), nullable=True),
        sa.Column('revived_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('revived_to_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('discarded_projects')
    op.drop_table('approval_logs')
    op.drop_table('bid_evaluation_reports')
    op.drop_table('owner_profiles')
    op.drop_column('ocr_extractions', 'standard_cert_suggestion')