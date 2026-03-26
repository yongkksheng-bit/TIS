"""Week 4 pricing models: CostEstimate, PricingDecision, PriceHistory."""
from sqlalchemy import String, Integer, Boolean, ForeignKey, Numeric, Text, Date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import Base
from decimal import Decimal
from datetime import date


class CostEstimate(Base):
    """Version-controlled cost breakdown per project."""
    __tablename__ = "cost_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    food_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    logistics_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    management_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    other_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal('0'))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    estimated_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    estimate_reason: Mapped[str] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class PricingDecision(Base):
    """Three-level pricing decision record per project."""
    __tablename__ = "pricing_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    cost_estimate_id: Mapped[int] = mapped_column(
        ForeignKey("cost_estimates.id"), nullable=True
    )
    cost_base: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    system_suggested_low: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    system_suggested_high: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    system_suggested_optimal: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    finance_suggested_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    finance_suggestion_reason: Mapped[str] = mapped_column(Text, nullable=True)
    boss_final_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    boss_decision_reason: Mapped[str] = mapped_column(Text, nullable=True)
    deviation_from_system: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)
    deviation_reason_category: Mapped[str] = mapped_column(String(50), nullable=True)
    budget_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    is_under_limit: Mapped[bool] = mapped_column(Boolean, nullable=True)
    limit_violation_warning: Mapped[str] = mapped_column(Text, nullable=True)
    game_theory_analysis: Mapped[dict] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='decided')


class PriceHistory(Base):
    """Historical bid data for cold-start pricing model."""
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_type: Mapped[str] = mapped_column(String(100), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    our_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    our_bid_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    winning_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=True)
    winning_unit: Mapped[str] = mapped_column(String(255), nullable=True)
    discount_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=True)
    bid_date: Mapped[date] = mapped_column(Date, nullable=True)
    is_our_win: Mapped[bool] = mapped_column(Boolean, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50), nullable=True)
