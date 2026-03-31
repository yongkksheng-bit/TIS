"""Week 10: add plan_code and agency_project_code to projects and tender_documents tables.

For precise duplicate detection using real tender document identifiers:
- plan_code: 采购计划编号 (e.g. 441301-2025-03605)
- agency_project_code: 采购项目编号 (e.g. HZJJ-2025118号, may be null)
"""
from alembic import op
import sqlalchemy as sa

revision = 'w010'
down_revision = 'w009'
branch_labels = None
depends_on = None


def upgrade():
    # projects table: precise duplicate-detection codes
    op.add_column('projects', sa.Column('plan_code', sa.String(length=50), nullable=True))
    op.add_column('projects', sa.Column('agency_project_code', sa.String(length=100), nullable=True))

    # tender_documents table: same codes extracted from PDF
    op.add_column('tender_documents', sa.Column('plan_code', sa.String(length=50), nullable=True))
    op.add_column('tender_documents', sa.Column('agency_project_code', sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column('tender_documents', 'agency_project_code')
    op.drop_column('tender_documents', 'plan_code')
    op.drop_column('projects', 'agency_project_code')
    op.drop_column('projects', 'plan_code')
