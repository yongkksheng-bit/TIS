"""Week 1 initial schema

Revision ID: w001
Revises:
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'w001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable vector extension for future embedding support
    op.execute('CREATE EXTENSION IF NOT EXISTS vector;')

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_name', sa.String(255), nullable=False),
        sa.Column('project_type', sa.String(50), nullable=True),
        sa.Column('owner_unit', sa.String(255), nullable=True),
        sa.Column('owner_type', sa.String(50), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('budget_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('bid_open_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='uploaded'),
        sa.Column('relationship_flag', sa.Boolean(), nullable=False, default=False),
        sa.Column('generation_mode', sa.String(20), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )

    # Create standard_certifications table
    op.create_table(
        'standard_certifications',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cert_code', sa.String(50), unique=True, nullable=False),
        sa.Column('cert_full_name', sa.String(255), nullable=False),
        sa.Column('cert_short_name', sa.String(100), nullable=True),
        sa.Column('aliases', JSONB, nullable=True),
        sa.Column('required_keywords', JSONB, nullable=False),
        sa.Column('exclude_keywords', JSONB, nullable=False),
        sa.Column('cert_number_pattern', sa.String(100), nullable=True),
        sa.Column('issuing_authority_keywords', JSONB, nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('validity_years', sa.Integer(), nullable=True),
        sa.Column('is_mandatory_for_food_delivery', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_mandatory_for_property', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )

    # Create tender_documents table
    op.create_table(
        'tender_documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_type', sa.String(10), nullable=True),
        sa.Column('parsing_status', sa.String(20), nullable=False, default='pending'),
        sa.Column('extracted_data', JSONB, nullable=True),
        sa.Column('parsed_by_ai', sa.Boolean(), nullable=False, default=False),
        sa.Column('confirmed_by_human', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.UniqueConstraint('project_id', name='uq_tender_documents_project_id'),
    )

    # Create bid_documents table
    op.create_table(
        'bid_documents',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doc_type', sa.String(50), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )

    # Create document_images table
    op.create_table(
        'document_images',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('bid_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('image_hash', sa.String(64), nullable=True),
        sa.Column('image_type', sa.String(50), nullable=False, default='other'),
        sa.Column('ocr_status', sa.String(20), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )

    # Create ocr_extractions table
    op.create_table(
        'ocr_extractions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('image_id', sa.Integer(), sa.ForeignKey('document_images.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_name', sa.String(50), nullable=False),
        sa.Column('field_value', sa.Text(), nullable=True),
        sa.Column('confidence_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('normalized_value', sa.Text(), nullable=True),
        sa.Column('standard_cert_id', sa.Integer(), sa.ForeignKey('standard_certifications.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_validated', sa.Boolean(), nullable=False, default=False),
        sa.Column('validated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('bbox_coords', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('ocr_extractions')
    op.drop_table('document_images')
    op.drop_table('bid_documents')
    op.drop_table('tender_documents')
    op.drop_table('standard_certifications')
    op.drop_table('projects')
