"""Week 5 formal review models."""
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from datetime import datetime
from typing import Optional


class FormalReviewItem(Base):
    """Dynamic checklist item for formal review."""
    __tablename__ = "formal_review_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("formal_review_items.id", ondelete="CASCADE"), nullable=True
    )
    check_category: Mapped[str] = mapped_column(String(50), nullable=False)
    check_title: Mapped[str] = mapped_column(String(255), nullable=False)
    check_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_clause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_status: Mapped[str] = mapped_column(String(20), nullable=False)
    system_evidence: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    specialist_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )
    specialist_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corrected_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pdf_highlight_coords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)


class AbandonedDraft(Base):
    """Archived drafts when boss terminates a project during review."""
    __tablename__ = "abandoned_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    termination_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tech_proposal_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    business_proposal_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pricing_decision_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pricing_decisions.id"), nullable=True
    )
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    termination_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    can_be_revived: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)
    revived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revived_to_project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )


class FinalBidDocument(Base):
    """Generated final bid documents."""
    __tablename__ = "final_bid_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)
    generation_status: Mapped[str] = mapped_column(
        String(20), default="generating", nullable=False
    )
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    packaging_guide: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
