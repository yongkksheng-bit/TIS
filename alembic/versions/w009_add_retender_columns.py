"""Week 9: add is_retender and parent_project_id to projects table for re-tender lineage tracking."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.schema import ForeignKey

revision = 'w009'
down_revision = 'w008'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('is_retender', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('projects', sa.Column('parent_project_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_projects_parent_project',
        'projects', 'projects',
        ['parent_project_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_projects_parent_project', 'projects', type_='foreignkey')
    op.drop_column('projects', 'parent_project_id')
    op.drop_column('projects', 'is_retender')
