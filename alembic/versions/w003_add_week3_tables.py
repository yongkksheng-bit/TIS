"""Week 3 tables: knowledge_chunks, tech_proposal_tasks, scoring_indexes, generation_logs

Revision ID: w003
Revises: w002
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = 'w003'
down_revision = 'w002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (PostgreSQL only)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # knowledge_chunks
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('chunk_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_vector', sa.Text(), nullable=True),  # JSON serialized for SQLite; pgvector for PostgreSQL
        sa.Column('chunk_metadata', JSON, nullable=False, default={}),
        sa.Column('source_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('is_deprecated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # tech_proposal_tasks
    op.create_table(
        'tech_proposal_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('generation_mode', sa.String(20), nullable=False),
        sa.Column('input_config', JSON, nullable=False, default={}),
        sa.Column('generated_content', JSON, nullable=True),
        sa.Column('final_content', sa.Text(), nullable=True),
        sa.Column('editor_version', sa.Integer(), default=1),
        sa.Column('status', sa.String(20), default='generating'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # scoring_indexes
    op.create_table(
        'scoring_indexes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score_item_name', sa.String(255), nullable=False),
        sa.Column('score_weight', sa.Numeric(5, 2), nullable=False),
        sa.Column('corresponding_section_id', sa.Integer(), nullable=True),
        sa.Column('corresponding_section_title', sa.String(255), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('keyword_matches', JSON, nullable=True),
        sa.Column('is_fully_responded', sa.Boolean(), default=False),
        sa.Column('evidence_paragraph_ids', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # generation_logs
    op.create_table(
        'generation_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tech_proposal_tasks.id', ondelete='CASCADE'), nullable=True),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=True),
        sa.Column('prompt_used', sa.Text(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(8, 4), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('generation_logs')
    op.drop_table('scoring_indexes')
    op.drop_table('tech_proposal_tasks')
    op.drop_table('knowledge_chunks')
