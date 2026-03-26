from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import Base, TimestampMixin


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_vector: Mapped[str] = mapped_column(Text, nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    source_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
