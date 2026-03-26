"""Week 6 review models for bid outcomes and knowledge evolution."""
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, Numeric, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from datetime import datetime, date
from typing import Optional


class BidOutcome(Base):
    """Bid outcome record for each project."""
    __tablename__ = "bid_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    outcome_status: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome_date: Mapped[date] = mapped_column(DateTime, nullable=False)
    final_bid_price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    winning_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    winning_unit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    our_price_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    disqualification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    disqualification_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    related_review_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("formal_review_items.id", ondelete="SET NULL"), nullable=True
    )
    is_manual_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)


class WinningDNA(Base):
    """Winning DNA extracted from successful bids."""
    __tablename__ = "winning_dna"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_chunk_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="SET NULL"), nullable=True
    )
    dna_type: Mapped[str] = mapped_column(String(50), nullable=False)
    score_contribution: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_item_matched: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    project_scale: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reused_in_projects: Mapped[Optional[str]] = mapped_column(JSON, nullable=True, default='[]')
    reuse_success_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)
    confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class DisqualificationTrap(Base):
    """Library of disqualification traps for prevention."""
    __tablename__ = "disqualification_traps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trap_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    trap_category: Mapped[str] = mapped_column(String(50), nullable=False)
    trap_title: Mapped[str] = mapped_column(String(255), nullable=False)
    trap_description: Mapped[str] = mapped_column(Text, nullable=False)
    detection_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_occurrence_project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prevention_checklist_item: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)


class DraftRevival(Base):
    """Revival of abandoned drafts for new bids."""
    __tablename__ = "draft_revivals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abandoned_draft_id: Mapped[int] = mapped_column(
        ForeignKey("abandoned_drafts.id", ondelete="CASCADE"), nullable=False
    )
    new_project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    revival_type: Mapped[str] = mapped_column(String(50), nullable=False)
    revived_content: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    adaptation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revived_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    revived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)
    is_successful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)


class KnowledgeEvolutionLog(Base):
    """Logs for knowledge chunk evolution tracking."""
    __tablename__ = "knowledge_evolution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    old_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=None)
