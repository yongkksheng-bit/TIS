"""w013: Create project_sections table for persistent section storage.

Revision ID: w013
Revises: w012
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'w013'
down_revision = 'w012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'project_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('section_name', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'section_name', name='uq_project_section_name'),
    )
    op.create_index('ix_project_sections_project_id', 'project_sections', ['project_id'])
    op.create_index('ix_project_sections_project_section', 'project_sections', ['project_id', 'section_name'])


def downgrade() -> None:
    op.drop_index('ix_project_sections_project_section', 'project_sections')
    op.drop_index('ix_project_sections_project_id', 'project_sections')
    op.drop_table('project_sections')
