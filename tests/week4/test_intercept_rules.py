"""TDD tests for PricingInterceptRules."""
import pytest
from decimal import Decimal
from app.core.week4_pricing.intercept_rules import PricingInterceptRules, InterceptResult


class TestPricingInterceptRules:
    def test_cost_inversion_warning(self):
        """total_cost > budget_limit * 0.95 → 成本倒挂警告."""
        rules = PricingInterceptRules()
        result = rules.check_cost_vs_budget(
            total_cost=Decimal('1450000'),
            budget_limit=Decimal('1500000'),
        )
        assert result.level == 'warning'
        assert '接近限价' in result.message

    def test_cost_ok_when_under_95_percent(self):
        """total_cost <= budget_limit * 0.95 → ok."""
        rules = PricingInterceptRules()
        result = rules.check_cost_vs_budget(
            total_cost=Decimal('1400000'),
            budget_limit=Decimal('1500000'),
        )
        assert result.level == 'ok'

    def test_loss_pricing_rejected(self):
        """boss_final < total_cost * 1.01 → error, blocked."""
        rules = PricingInterceptRules()
        result = rules.check_final_price(
            final_price=Decimal('99000'),
            total_cost=Decimal('100000'),
        )
        assert result.level == 'error'
        assert '亏损' in result.message

    def test_profit_margin_1_percent_accepted(self):
        """boss_final >= total_cost * 1.01 → not blocked as loss."""
        rules = PricingInterceptRules()
        result = rules.check_final_price(
            final_price=Decimal('101000'),
            total_cost=Decimal('100000'),
        )
        assert result.level != 'error'  # passes loss check

    def test_over_limit_requires_confirmation(self):
        """boss_final > budget_limit → over_limit, requires_confirmation."""
        rules = PricingInterceptRules()
        result = rules.check_final_price(
            final_price=Decimal('1600000'),
            total_cost=Decimal('1000000'),
            budget_limit=Decimal('1500000'),
        )
        assert result.level == 'over_limit'
        assert result.requires_confirmation is True
        assert '超过限价' in result.message

    def test_deviation_over_5_percent_requires_reason(self):
        """|boss_final - system_optimal| / system_optimal > 0.05 → requires_reason."""
        rules = PricingInterceptRules()
        result = rules.check_final_price(
            final_price=Decimal('115000'),
            total_cost=Decimal('100000'),
            budget_limit=Decimal('1500000'),
            system_optimal=Decimal('108000'),
        )
        assert result.requires_reason is True
        assert result.deviation_pct > Decimal('0.05')

    def test_deviation_under_5_percent_no_reason(self):
        """|boss_final - system_optimal| / system_optimal <= 0.05 → ok."""
        rules = PricingInterceptRules()
        result = rules.check_final_price(
            final_price=Decimal('109000'),
            total_cost=Decimal('100000'),
            budget_limit=Decimal('1500000'),
            system_optimal=Decimal('108000'),
        )
        assert result.requires_reason is False
        assert result.level == 'ok'

    def test_normal_pricing_all_checks_pass(self):
        """Normal price: profit OK, under limit, deviation OK → level=ok."""
        rules = PricingInterceptRules()
        result = rules.check_final_price(
            final_price=Decimal('110000'),
            total_cost=Decimal('100000'),
            budget_limit=Decimal('1500000'),
            system_optimal=Decimal('108000'),
        )
        assert result.level == 'ok'
        assert result.requires_confirmation is False
        assert result.requires_reason is False

    def test_check_deviation_standalone(self):
        """check_deviation() correctly identifies >5% deviation."""
        rules = PricingInterceptRules()
        result = rules.check_deviation(
            boss_final=Decimal('120000'),
            system_optimal=Decimal('100000'),
        )
        assert result.requires_reason is True
        assert result.deviation_pct == Decimal('0.2')

    def test_intercept_result_dataclass(self):
        """InterceptResult has correct fields with defaults."""
        r = InterceptResult(level='ok')
        assert r.level == 'ok'
        assert r.message == ""
        assert r.requires_confirmation is False
        assert r.requires_reason is False
        assert r.deviation_pct == Decimal('0')
