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


class ConfirmedCostEstimateResponse(BaseModel):
    """Confirmed cost estimate with full breakdown for the pricing page."""
    id: int
    project_id: int
    version_number: int
    food_cost: Decimal
    logistics_cost: Decimal
    labor_cost: Decimal
    management_cost: Decimal
    other_cost: Decimal
    total_cost: Decimal
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


class PricingDecisionUpsertRequest(BaseModel):
    """
    Upsert a pricing decision for a project.

    This is the unified endpoint for both specialist draft saves and boss final submissions.
    Supports unlimited overwrites as long as the project has not reached formal_review stage.

    action_type:
      - 'specialist_draft': Specialist saves their proposed price (status → awaiting_pricing, no boss involved)
      - 'submit_to_boss': Specialist requests boss decision (status → pending_boss_approval)
      - 'boss_final': Boss confirms final price (status → formal_review)

    Either boss_final_price OR specialist_price must be provided depending on action_type.
    """
    action_type: str = Field(
        ...,
        pattern="^(specialist_draft|submit_to_boss|boss_final)$",
        description="'specialist_draft' | 'submit_to_boss' | 'boss_final'"
    )
    price: Decimal = Field(..., gt=Decimal('0'), description="报价金额")
    notes: Optional[str] = Field(None, description="定价说明（可选）")
    deviation_reason: Optional[str] = Field(None, description="偏离系统建议价的原因说明（boss_final时必填，超5%偏离）")


class PricingDecisionResponse(BaseModel):
    """Response after submitting a pricing decision."""
    id: int
    project_id: int
    specialist_price: Optional[Decimal]
    boss_final_price: Optional[Decimal]
    status: str
    action_type: str
    deviation_from_system: Optional[Decimal]
    new_project_status: str

    model_config = ConfigDict(from_attributes=True)


class MarketBenchmarkData(BaseModel):
    """
    Market benchmark statistics from historical bid data.

    Returned in the pricing dashboard so analysts can see
    historical discount rates, bidder counts, and win rates
    for the same region + project_type before deciding on a price.

    All numeric fields are Optional — None means insufficient historical data.
    """
    region: str
    project_type: str
    avg_discount_rate: Optional[float] = Field(
        None, description="历史平均下浮率（winning_price / budget_amount）。None=无数据"
    )
    median_discount_rate: Optional[float] = Field(
        None, description="历史下浮率中位数，更抗异常值干扰"
    )
    bidder_count_avg: Optional[float] = Field(
        None, description="历史平均投标家数"
    )
    bidder_count_median: Optional[float] = Field(
        None, description="历史投标家数中位数"
    )
    expected_competitive_price: Optional[float] = Field(
        None,
        description="期望竞争价 = budget * avg_discount_rate（参考历史均衡价）",
    )
    historical_win_rate: Optional[float] = Field(
        None, description="我司历史中标率。None=无数据"
    )
    sample_size: int = Field(
        0, description="用于统计的历史投标记录数量"
    )
    avg_price_gap_pct: Optional[float] = Field(
        None,
        description="我司历史平均报价差距百分比（正数=我们报价偏高）",
    )
    price_gap_bucket_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="报价差距分段分布：overpriced/slightly_high/winning/underpriced",
    )
    has_data: bool = Field(
        False, description="是否有可用的历史数据（sample_size > 0）"
    )


class PricingDashboardResponse(BaseModel):
    """Response for the pricing dashboard overview."""
    project_id: int
    cost_base: Optional[Decimal]
    budget_limit: Optional[Decimal]
    scenarios: list[PriceScenario]
    market_benchmark: Optional[MarketBenchmarkData] = Field(
        None,
        description="市场基准数据（同地区同类型历史项目统计）。无数据时为 null",
    )