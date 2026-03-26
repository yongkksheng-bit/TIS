"""Week 4 Pydantic schemas for pricing API endpoints."""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
from decimal import Decimal


class CostEstimateCreate(BaseModel):
    """Request to create a cost estimate."""
    food_cost: Decimal = Field(..., ge=Decimal('0'), description="食材成本")
    logistics_cost: Decimal = Field(..., ge=Decimal('0'), description="物流成本")
    labor_cost: Decimal = Field(..., ge=Decimal('0'), description="人工成本")
    management_cost: Decimal = Field(..., ge=Decimal('0'), description="管理成本")
    other_cost: Decimal = Field(default=Decimal('0'), ge=Decimal('0'), description="其他成本")
    estimate_reason: str = Field(..., min_length=1, description="测算依据说明")


class CostEstimateResponse(BaseModel):
    """Response after creating a cost estimate."""
    id: int
    version_number: int
    total_cost: Decimal
    breakdown: dict
    estimated_by: int
    is_confirmed: bool

    model_config = ConfigDict(from_attributes=True)


class PriceScenario(BaseModel):
    """Single pricing scenario (aggressive/balanced/conservative)."""
    scenario: str
    price: Decimal
    label: str
    win_prob: Decimal
    profit: Decimal
    expected_value: Decimal
    risk_level: str
    is_recommended: bool = False


class PricingCalculationResponse(BaseModel):
    """Response from pricing calculation (A/B/C scenarios)."""
    project_id: int
    cost_base: Decimal
    budget_limit: Optional[Decimal]
    scenarios: list[PriceScenario]
    optimal_recommendation: PriceScenario


class PricingDecisionCreate(BaseModel):
    """Request to submit a pricing decision (boss final price)."""
    boss_final_price: Decimal = Field(..., gt=Decimal('0'), description="老板最终定价")
    boss_decision_reason: str = Field(..., min_length=1, description="决策理由")
    deviation_reason_category: Optional[str] = Field(
        None,
        description="差异原因分类: competition_intelligence/profit_reserve/relationship_leverage/other"
    )
    finance_suggested_price: Optional[Decimal] = Field(None, gt=Decimal('0'), description="财务建议价")
    finance_suggestion_reason: Optional[str] = Field(None, description="财务建议理由")

    @field_validator('boss_decision_reason')
    @classmethod
    def reason_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('boss_decision_reason cannot be empty or whitespace')
        return v


class PricingDecisionResponse(BaseModel):
    """Response after submitting a pricing decision."""
    id: int
    project_id: int
    boss_final_price: Decimal
    status: str
    deviation_from_system: Optional[Decimal]

    model_config = ConfigDict(from_attributes=True)


class PricingDashboardResponse(BaseModel):
    """Response for the pricing dashboard overview."""
    project_id: int
    cost_base: Optional[Decimal]
    budget_limit: Optional[Decimal]
    scenarios: list[PriceScenario]