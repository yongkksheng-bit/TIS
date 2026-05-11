"""Historical asset models — hard-isolated from live Project table.

These tables store completed tenders and bids for RAG enrichment
and pricing benchmark analytics. They NEVER appear in the active
Project list and are never part of the OLTP workflow.
"""
from sqlalchemy import String, Boolean, ForeignKey, Numeric, Date, DateTime, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from datetime import datetime
from typing import Optional, List

from app.models.base import Base, TimestampMixin


class HistoricalTender(Base, TimestampMixin):
    """
    Historical tender招标文件归档。
    One record per historical tender procurement.
    """

    __tablename__ = "historical_tenders"

    # ── Core identification ──────────────────────────────────────────
    project_name: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_unit: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)       # 地级市
    province: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)       # 省份
    project_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)    # service/goods/engineering

    # ── Financial ────────────────────────────────────────────────────
    budget_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY", nullable=False)
    winning_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)   # ← 金线字段
    winning_price_usd: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    price_revealed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Timeline ─────────────────────────────────────────────────────
    bid_open_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    submission_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    estimated_duration_months: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # ── Procurement codes ────────────────────────────────────────────
    plan_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agency_project_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Winner / status ─────────────────────────────────────────────
    winning_bidder: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tender_status: Mapped[str] = mapped_column(
        String(20), default="closed", nullable=False
    )  # ongoing / closed / awarded / cancelled

    # ── File storage ──────────────────────────────────────────────────
    tender_file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tender_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256

    # ── Structured metadata ─────────────────────────────────────────
    scoring_criteria_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ── Provenance ───────────────────────────────────────────────────
    imported_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    imported_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    # ── Relationships ───────────────────────────────────────────────
    bids: Mapped[List["HistoricalBid"]] = relationship(
        "HistoricalBid", back_populates="tender", cascade="all, delete-orphan"
    )

    # ── Indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        # Unique constraint: prevent importing the same file twice
        # UniqueConstraint('tender_file_hash', name='uq_ht_file_hash'),
    )


class HistoricalBid(Base, TimestampMixin):
    """
    Historical bid — our company's historical bid record for a historical tender.
    One record per (tender × bidder) combination.
    """

    __tablename__ = "historical_bids"

    # ── FK ──────────────────────────────────────────────────────────
    historical_tender_id: Mapped[int] = mapped_column(
        ForeignKey("historical_tenders.id", ondelete="CASCADE"), nullable=False
    )

    # ── Our bid data ────────────────────────────────────────────────
    our_bid_price: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    our_bid_submission_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    our_bid_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # won / lost / abandoned / pending

    # ── Competitive position ─────────────────────────────────────────
    price_gap_percentage: Mapped[Optional[float]] = mapped_column(
        Numeric(8, 4), nullable=True
    )   # (M - W) / W × 100
    price_gap_bucket: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )   # overpriced / slightly_high / winning / underpriced
    win_rank: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    total_bidders_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    is_sole_bidder: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Postmortem linkage ──────────────────────────────────────────
    internal_postmortem_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("internal_postmortems.id", ondelete="SET NULL"), nullable=True
    )
    bid_file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_postmortem_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Relationships ────────────────────────────────────────────────
    tender: Mapped["HistoricalTender"] = relationship(
        "HistoricalTender", back_populates="bids"
    )
    postmortem: Mapped[Optional["InternalPostmortem"]] = relationship(
        "InternalPostmortem",
        foreign_keys=[internal_postmortem_id],
    )

    # ── Indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        # UniqueConstraint: one bid record per (tender × bidder) pair
        # UniqueConstraint('historical_tender_id', name='uq_hb_tender_bidder'),
    )


class InternalPostmortem(Base, TimestampMixin):
    """
    Internal postmortem — structured lessons learned from a historical bid outcome.
    The expert feedback text is chunked and stored in knowledge_chunks
    for dual-track RAG retrieval.
    """

    __tablename__ = "internal_postmortems"

    # ── FK ──────────────────────────────────────────────────────────
    historical_bid_id: Mapped[int] = mapped_column(
        ForeignKey("historical_bids.id", ondelete="CASCADE"), nullable=False
    )

    # ── Outcome ─────────────────────────────────────────────────────
    outcome: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # WIN / LOSS / PARTIAL_WIN

    # ── Scores (if publicly disclosed) ────────────────────────────────
    score_received: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    score_max: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    technical_score_received: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    price_score_received: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)

    # ── Structured tags (array) ─────────────────────────────────────
    key_win_factors: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    key_loss_factors: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    loss_root_cause_tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    win_breakthrough_tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(50)), nullable=True
    )

    # ── Expert feedback text ─────────────────────────────────────────
    expert_feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Confidentiality ───────────────────────────────────────────────
    confidential_level: Mapped[str] = mapped_column(
        String(20), default="internal", nullable=False
    )  # 绝密 / internal / public

    # ── Relationships ────────────────────────────────────────────────
    bid: Mapped["HistoricalBid"] = relationship(
        "HistoricalBid",
        foreign_keys=[historical_bid_id],
    )

    # ── Indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        # One postmortem per bid
        # UniqueConstraint('historical_bid_id', name='uq_ip_bid'),
    )
