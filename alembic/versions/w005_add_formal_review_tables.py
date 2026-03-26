"""Week 5: formal_review_items, abandoned_drafts, final_bid_documents."""
from alembic import op
import sqlalchemy as sa

revision = 'w005'
down_revision = 'w004'
branch_labels = None
depends_on = None


def upgrade():
    # formal_review_items
    op.create_table(
        'formal_review_items',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('parent_item_id', sa.Integer(),
                  sa.ForeignKey('formal_review_items.id', ondelete='CASCADE'), nullable=True),
        sa.Column('check_category', sa.String(50), nullable=False),
        sa.Column('check_title', sa.String(255), nullable=False),
        sa.Column('check_description', sa.Text(), nullable=True),
        sa.Column('reference_clause', sa.Text(), nullable=True),
        sa.Column('system_status', sa.String(20), nullable=False),
        sa.Column('system_evidence', sa.JSON(), nullable=True),
        sa.Column('specialist_status', sa.String(20), nullable=False, default='pending'),
        sa.Column('specialist_notes', sa.Text(), nullable=True),
        sa.Column('corrected_evidence', sa.Text(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('pdf_highlight_coords', sa.JSON(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(),
                  onupdate=sa.func.now(), nullable=True),
        sa.CheckConstraint("source_type IN ('system_parsed','ocr_comparison','content_integrity','manual_added')"),
        sa.CheckConstraint("check_category IN ('qualification_validity','signature_seal','document_integrity','price_compliance','seal_requirement','format_compliance')"),
        sa.CheckConstraint("system_status IN ('passed','failed','warning','uncertain')"),
        sa.CheckConstraint("specialist_status IN ('pending','confirmed','corrected','deleted')"),
        sa.CheckConstraint("risk_level IN ('fatal','warning','info')"),
    )

    # abandoned_drafts
    op.create_table(
        'abandoned_drafts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('termination_stage', sa.String(50), nullable=True),
        sa.Column('tech_proposal_path', sa.String(500), nullable=True),
        sa.Column('business_proposal_path', sa.String(500), nullable=True),
        sa.Column('pricing_decision_id', sa.Integer(),
                  sa.ForeignKey('pricing_decisions.id'), nullable=True),
        sa.Column('termination_reason', sa.Text(), nullable=True),
        sa.Column('termination_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('can_be_revived', sa.Boolean(), default=True, nullable=False),
        sa.Column('archived_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('revived_at', sa.DateTime(), nullable=True),
        sa.Column('revived_to_project_id', sa.Integer(),
                  sa.ForeignKey('projects.id'), nullable=True),
        sa.CheckConstraint("termination_stage IN ('formal_review','pricing','tech_generation')"),
    )

    # final_bid_documents
    op.create_table(
        'final_bid_documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('generated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('generated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('generation_status', sa.String(20), nullable=False, default='generating'),
        sa.Column('error_log', sa.Text(), nullable=True),
        sa.Column('packaging_guide', sa.JSON(), nullable=True),
        sa.CheckConstraint("document_type IN ('complete','technical_volume','business_volume')"),
        sa.CheckConstraint("generation_status IN ('generating','completed','failed')"),
    )


def downgrade():
    op.drop_table('final_bid_documents')
    op.drop_table('abandoned_drafts')
    op.drop_table('formal_review_items')
