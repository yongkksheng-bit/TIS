from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import Base, TimestampMixin
import sqlalchemy as sa
from datetime import datetime


class TechProposalTask(Base, TimestampMixin):
    __tablename__ = "tech_proposal_tasks"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    input_config: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    generated_content: Mapped[dict] = mapped_column(JSON, nullable=True)
    final_content: Mapped[str] = mapped_column(Text, nullable=True)
    editor_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default='generating')
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)


class ScoringIndex(Base):
    __tablename__ = "scoring_indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    score_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    score_weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    corresponding_section_id: Mapped[int] = mapped_column(Integer, nullable=True)
    corresponding_section_title: Mapped[str] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    keyword_matches: Mapped[list] = mapped_column(JSON, nullable=True)
    is_fully_responded: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_paragraph_ids: Mapped[list] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=sa.func.now())


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tech_proposal_tasks.id", ondelete="CASCADE"), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    section_id: Mapped[int] = mapped_column(Integer, nullable=True)
    prompt_used: Mapped[str] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=sa.func.now())
