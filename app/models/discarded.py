from sqlalchemy import String, Integer, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
from datetime import datetime

class DiscardedProject(Base, TimestampMixin):
    __tablename__ = "discarded_projects"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    original_evaluation_report_id: Mapped[int] = mapped_column(ForeignKey("bid_evaluation_reports.id"), nullable=True)
    discarded_by: Mapped[str] = mapped_column(String(50), nullable=False)
    discard_reason: Mapped[str] = mapped_column(Text, nullable=True)
    discard_stage: Mapped[str] = mapped_column(String(50), nullable=True)
    can_be_revived: Mapped[bool] = mapped_column(Boolean, default=True)
    revived_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    revived_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    revived_to_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=True)