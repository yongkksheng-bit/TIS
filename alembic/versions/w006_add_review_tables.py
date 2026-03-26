"""Week 6: bid_outcomes, winning_dna, disqualification_traps, draft_revivals, knowledge_evolution_logs."""
from alembic import op
import sqlalchemy as sa

revision = 'w006'
down_revision = 'w005'
branch_labels = None
depends_on = None


def upgrade():
    # bid_outcomes
    op.create_table(
        'bid_outcomes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('outcome_status', sa.String(20), nullable=False),
        sa.Column('outcome_date', sa.Date(), nullable=False),
        sa.Column('final_bid_price', sa.Numeric(15, 2), nullable=False),
        sa.Column('winning_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('winning_unit', sa.String(255), nullable=True),
        sa.Column('our_price_rank', sa.Integer(), nullable=True),
        sa.Column('disqualification_reason', sa.Text(), nullable=True),
        sa.Column('disqualification_type', sa.String(50), nullable=True),
        sa.Column('related_review_item_id', sa.Integer(),
                  sa.ForeignKey('formal_review_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_manual_error', sa.Boolean(), default=False, nullable=False),
        sa.Column('review_analysis', sa.JSON(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("outcome_status IN ('win','lose','disqualified','abandoned','withdrawn')"),
        sa.CheckConstraint("disqualification_type IN ('fatal_formal','fatal_qualification','fatal_price','tech_deficiency','price_uncompetitive') OR disqualification_type IS NULL"),
    )

    # winning_dna
    op.create_table(
        'winning_dna',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_chunk_id', sa.Integer(),
                  sa.ForeignKey('knowledge_chunks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('dna_type', sa.String(50), nullable=False),
        sa.Column('score_contribution', sa.Integer(), nullable=False),
        sa.Column('scoring_item_matched', sa.String(255), nullable=True),
        sa.Column('owner_type', sa.String(50), nullable=True),
        sa.Column('project_scale', sa.String(50), nullable=True),
        sa.Column('reused_in_projects', sa.JSON(), nullable=True, default='[]'),
        sa.Column('reuse_success_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('extracted_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.CheckConstraint("dna_type IN ('high_score_response','winning_price_strategy','effective_case_usage','format_excellence')"),
        sa.CheckConstraint("score_contribution BETWEEN 1 AND 10"),
    )

    # disqualification_traps
    op.create_table(
        'disqualification_traps',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('trap_code', sa.String(50), nullable=False, unique=True),
        sa.Column('trap_category', sa.String(50), nullable=False),
        sa.Column('trap_title', sa.String(255), nullable=False),
        sa.Column('trap_description', sa.Text(), nullable=False),
        sa.Column('detection_method', sa.Text(), nullable=True),
        sa.Column('first_occurrence_project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('occurrence_count', sa.Integer(), default=1, nullable=False),
        sa.Column('prevention_checklist_item', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("trap_category IN ('signature','seal','qualification','price','format','timing')"),
    )

    # draft_revivals
    op.create_table(
        'draft_revivals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('abandoned_draft_id', sa.Integer(),
                  sa.ForeignKey('abandoned_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('new_project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('revival_type', sa.String(50), nullable=False),
        sa.Column('revived_content', sa.JSON(), nullable=True),
        sa.Column('adaptation_notes', sa.Text(), nullable=True),
        sa.Column('revived_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('revived_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('is_successful', sa.Boolean(), nullable=True),
        sa.CheckConstraint("revival_type IN ('rebid_same_project','similar_project_reference')"),
    )

    # knowledge_evolution_logs
    op.create_table(
        'knowledge_evolution_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chunk_id', sa.Integer(),
                  sa.ForeignKey('knowledge_chunks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('old_quality_score', sa.Integer(), nullable=True),
        sa.Column('new_quality_score', sa.Integer(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("action_type IN ('created','weighted','deprecated','reused','confirmed_win','confirmed_lose')"),
    )


def downgrade():
    op.drop_table('knowledge_evolution_logs')
    op.drop_table('draft_revivals')
    op.drop_table('disqualification_traps')
    op.drop_table('winning_dna')
    op.drop_table('bid_outcomes')
