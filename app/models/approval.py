from sqlalchemy import String, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
from app.models.enums import ApprovalAction

class ApprovalLog(Base, TimestampMixin):
    __tablename__ = "approval_logs"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    action_type: Mapped[ApprovalAction] = mapped_column(String(50), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason_text: Mapped[str] = mapped_column(Text, nullable=True)
    original_status: Mapped[str] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=True)