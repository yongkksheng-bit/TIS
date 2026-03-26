"""TDD tests for Week 4 Pydantic schemas."""
import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.week4 import (
    CostEstimateCreate,
    CostEstimateResponse,
    PriceScenario,
    PricingCalculationResponse,
    PricingDecisionCreate,
    PricingDecisionResponse,
)


class TestCostEstimateCreate:
    def test_valid_cost_estimate(self):
        data = CostEstimateCreate(
            food_cost=Decimal('100000'),
            logistics_cost=Decimal('20000'),
            labor_cost=Decimal('50000'),
            management_cost=Decimal('20000'),
            estimate_reason="基于历史数据测算",
        )
        assert data.food_cost == Decimal('100000')
        assert data.other_cost == Decimal('0')  # default

    def test_negative_cost_rejected(self):
        with pytest.raises(ValidationError):
            CostEstimateCreate(
                food_cost=Decimal('-1000'),
                logistics_cost=Decimal('20000'),
                labor_cost=Decimal('50000'),
                management_cost=Decimal('20000'),
                estimate_reason="Invalid",
            )

    def test_empty_reason_rejected(self):
        with pytest.raises(ValidationError):
            CostEstimateCreate(
                food_cost=Decimal('100000'),
                logistics_cost=Decimal('20000'),
                labor_cost=Decimal('50000'),
                management_cost=Decimal('20000'),
                estimate_reason="",
            )


class TestPriceScenario:
    def test_scenario_recommended_flag_default_false(self):
        scenario = PriceScenario(
            scenario="aggressive",
            price=Decimal('103000'),
            label="激进策略（成本+3%）",
            win_prob=Decimal('0.8'),
            profit=Decimal('3000'),
            expected_value=Decimal('2400'),
            risk_level="low",
        )
        assert scenario.is_recommended is False

    def test_scenario_with_recommended_true(self):
        scenario = PriceScenario(
            scenario="balanced",
            price=Decimal('108000'),
            label="平衡策略（成本+8%）",
            win_prob=Decimal('0.6'),
            profit=Decimal('8000'),
            expected_value=Decimal('4800'),
            risk_level="medium",
            is_recommended=True,
        )
        assert scenario.is_recommended is True


class TestPricingDecisionCreate:
    def test_boss_final_price_required(self):
        """boss_final_price is mandatory."""
        with pytest.raises(ValidationError):
            PricingDecisionCreate(boss_decision_reason="测试理由")

    def test_boss_decision_reason_required(self):
        """boss_decision_reason is mandatory."""
        with pytest.raises(ValidationError):
            PricingDecisionCreate(boss_final_price=Decimal('110000'))

    def test_whitespace_reason_rejected(self):
        """Whitespace-only boss_decision_reason is rejected."""
        with pytest.raises(ValidationError):
            PricingDecisionCreate(
                boss_final_price=Decimal('110000'),
                boss_decision_reason="   ",
            )

    def test_finance_suggested_price_optional(self):
        """finance_suggested_price is optional."""
        d = PricingDecisionCreate(
            boss_final_price=Decimal('110000'),
            boss_decision_reason="适中定价",
        )
        assert d.finance_suggested_price is None
        assert d.finance_suggested_price is None

    def test_deviation_category_optional(self):
        d = PricingDecisionCreate(
            boss_final_price=Decimal('110000'),
            boss_decision_reason="适中定价",
            deviation_reason_category="profit_reserve",
        )
        assert d.deviation_reason_category == "profit_reserve"