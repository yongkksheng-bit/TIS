from sqlalchemy import String, Integer, ForeignKey, DECIMAL, JSON, DateTime, Boolean, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
from app.models.enums import TimeUrgencyLevel, RiskLevel, Recommendation, CostConfidence
from datetime import datetime

class BidEvaluationReport(Base, TimestampMixin):
    __tablename__ = "bid_evaluation_reports"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    report_version: Mapped[int] = mapped_column(Integer, default=1)
    qualification_match_score: Mapped[int] = mapped_column(Integer, nullable=True)
    missing_mandatory_certs: Mapped[list] = mapped_column(JSON, nullable=True)
    missing_optional_certs: Mapped[list] = mapped_column(JSON, nullable=True)
    matched_certs_detail: Mapped[list] = mapped_column(JSON, nullable=True)
    days_until_bid_open: Mapped[int] = mapped_column(Integer, nullable=True)
    time_urgency_level: Mapped[TimeUrgencyLevel] = mapped_column(String(20), nullable=True)
    is_time_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=True)
    owner_profile_id: Mapped[int] = mapped_column(ForeignKey("owner_profiles.id"), nullable=True)
    relationship_index: Mapped[int] = mapped_column(Integer, nullable=True)
    is_new_owner: Mapped[bool] = mapped_column(Boolean, nullable=True)
    estimated_cost: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=True)
    suggested_price_range_low: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=True)
    suggested_price_range_high: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=True)
    cost_estimate_confidence: Mapped[CostConfidence] = mapped_column(String(20), nullable=True)
    overall_win_probability: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=True)
    risk_level: Mapped[RiskLevel] = mapped_column(String(20), nullable=True)
    fatal_risks: Mapped[list] = mapped_column(JSON, nullable=True)
    warning_risks: Mapped[list] = mapped_column(JSON, nullable=True)
    recommendation: Mapped[Recommendation] = mapped_column(String(20), nullable=True)
    recommendation_reason: Mapped[str] = mapped_column(String(500), nullable=True)
    generated_by: Mapped[str] = mapped_column(String(50), default='system')
    confirmed_by_specialist: Mapped[bool] = mapped_column(Boolean, default=False)
    specialist_decision: Mapped[str] = mapped_column(String(20), nullable=True)
    specialist_notes: Mapped[str] = mapped_column(String(500), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    overridden_by_boss: Mapped[bool] = mapped_column(Boolean, default=False)
    boss_override_reason: Mapped[str] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint('project_id', 'report_version'),
        CheckConstraint('qualification_match_score BETWEEN 0 AND 100'),
        CheckConstraint('relationship_index BETWEEN 0 AND 100'),
    )