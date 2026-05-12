from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON, ARRAY

from app.models.base import Base, TimestampMixin


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_vector: Mapped[str] = mapped_column(Text, nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    source_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── w015: historical asset RAG columns ─────────────────────────────────
    source_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_signal: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="positive=成功经验 | negative=失败教训 | neutral=一般参考",
    )
    scoring_dimension_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True,
        comment="评分维度标签，如['食材溯源','冷链管理']",
    )
    region_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True,
        comment="地区标签，如['广东省','惠州市']",
    )
    project_type_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True,
        comment="项目类型标签，如['服务类','食堂配送']",
    )
    is_price_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
