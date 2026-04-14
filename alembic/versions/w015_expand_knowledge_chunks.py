"""w015: Expand knowledge_chunks for historical asset RAG support.

Revision ID: w015
Revises: w014
Create Date: 2026-04-13

Adds structured metadata columns to support dual-track RAG retrieval
(positive winning samples vs. negative loss lessons) for historical tenders.

向下兼容原则：仅 ADD 列，不改现有列，不删任何字段。
所有新列均为 nullable=True，不对历史数据施加 NOT NULL 约束。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


revision = 'w015'
down_revision = 'w014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('knowledge_chunks',
        sa.Column('source_type', sa.String(30), nullable=True))
    op.add_column('knowledge_chunks',
        sa.Column('source_id', sa.BigInteger, nullable=True))
    op.add_column('knowledge_chunks',
        sa.Column('source_label', sa.String(255), nullable=True))
    op.add_column('knowledge_chunks',
        sa.Column('chunk_index', sa.Integer, nullable=True))
    op.add_column('knowledge_chunks',
        sa.Column('win_signal', sa.String(20), nullable=True,
                  comment="positive=成功经验 | negative=失败教训 | neutral=一般参考"))
    op.add_column('knowledge_chunks',
        sa.Column('scoring_dimension_tags', ARRAY(sa.String(50), dimensions=1),
                  nullable=True,
                  comment="评分维度标签，如['食材溯源','冷链管理']"))
    op.add_column('knowledge_chunks',
        sa.Column('region_tags', ARRAY(sa.String(50), dimensions=1),
                  nullable=True,
                  comment="地区标签，如['广东省','惠州市']"))
    op.add_column('knowledge_chunks',
        sa.Column('project_type_tags', ARRAY(sa.String(50), dimensions=1),
                  nullable=True,
                  comment="项目类型标签，如['服务类','食堂配送']"))
    op.add_column('knowledge_chunks',
        sa.Column('is_price_sensitive', sa.Boolean, default=False, nullable=False))
    op.add_column('knowledge_chunks',
        sa.Column('token_count', sa.Integer, nullable=True))

    # 索引：支持 WHERE 过滤常见组合
    op.create_index('ix_kc_source_type', 'knowledge_chunks', ['source_type'])
    op.create_index('ix_kc_win_signal', 'knowledge_chunks', ['win_signal'])
    op.create_index('ix_kc_price_sensitive', 'knowledge_chunks', ['is_price_sensitive'])


def downgrade() -> None:
    # 仅删除新增列，保留原有表结构（零破坏）
    op.drop_index('ix_kc_price_sensitive', table_name='knowledge_chunks')
    op.drop_index('ix_kc_win_signal', table_name='knowledge_chunks')
    op.drop_index('ix_kc_source_type', table_name='knowledge_chunks')

    op.drop_column('knowledge_chunks', 'token_count')
    op.drop_column('knowledge_chunks', 'is_price_sensitive')
    op.drop_column('knowledge_chunks', 'project_type_tags')
    op.drop_column('knowledge_chunks', 'region_tags')
    op.drop_column('knowledge_chunks', 'scoring_dimension_tags')
    op.drop_column('knowledge_chunks', 'win_signal')
    op.drop_column('knowledge_chunks', 'chunk_index')
    op.drop_column('knowledge_chunks', 'source_label')
    op.drop_column('knowledge_chunks', 'source_id')
    op.drop_column('knowledge_chunks', 'source_type')
