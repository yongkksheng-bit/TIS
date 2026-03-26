"""TDD tests for PricingGameTheoryModel."""
import pytest
from decimal import Decimal
from app.core.week4_pricing.game_theory import PricingGameTheoryModel


class TestPricingGameTheoryModel:
    def test_aggressive_scenario_cost_plus_3_percent(self):
        """激进场景 = cost * 1.03."""
        model = PricingGameTheoryModel(
            cost=Decimal('100000'),
            budget=Decimal('150000'),
            price_score_weight=Decimal('0.3'),
            relationship_index=50,
        )
        scenarios = model.generate_price_scenarios()
        aggressive = next(s for s in scenarios if s['scenario'] == 'aggressive')
        assert aggressive['price'] == Decimal('103000.00')

    def test_balanced_scenario_cost_plus_8_percent(self):
        """平衡场景 = cost * 1.08."""
        model = PricingGameTheoryModel(
            cost=Decimal('100000'),
            budget=Decimal('150000'),
        )
        scenarios = model.generate_price_scenarios()
        balanced = next(s for s in scenarios if s['scenario'] == 'balanced')
        assert balanced['price'] == Decimal('108000.00')

    def test_conservative_scenario_cost_plus_15_percent(self):
        """保守场景 = cost * 1.15."""
        model = PricingGameTheoryModel(
            cost=Decimal('100000'),
            budget=Decimal('150000'),
        )
        scenarios = model.generate_price_scenarios()
        conservative = next(s for s in scenarios if s['scenario'] == 'conservative')
        assert conservative['price'] == Decimal('115000.00')

    def test_optimal_is_highest_expected_value(self):
        """推荐最优 = 期望收益最高的场景."""
        model = PricingGameTheoryModel(
            cost=Decimal('100000'),
            budget=Decimal('150000'),
        )
        scenarios = model.generate_price_scenarios()
        optimal = next(s for s in scenarios if s.get('is_recommended'))
        expected_values = [s['expected_value'] for s in scenarios]
        assert optimal['expected_value'] == max(expected_values)

    def test_relationship_guarantee_75_percent(self):
        """有关系(relationship_index>=80)项目至少75%保底概率."""
        model = PricingGameTheoryModel(
            cost=Decimal('100000'),
            budget=Decimal('150000'),
            relationship_index=85,
        )
        # At a reasonable price, win_prob should be at least 0.75
        prob = model.calculate_win_probability(Decimal('115000'))
        assert prob['win_probability'] >= Decimal('0.75')
