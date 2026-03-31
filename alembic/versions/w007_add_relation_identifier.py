"""Week 7: add relation_identifier and differentiation_guidance to projects table."""
from alembic import op
import sqlalchemy as sa

revision = 'w007'
down_revision = 'w006'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('projects', sa.Column('relation_identifier', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('differentiation_guidance', sa.String(1000), nullable=True))


def downgrade():
    op.drop_column('projects', 'differentiation_guidance')
    op.drop_column('projects', 'relation_identifier')
