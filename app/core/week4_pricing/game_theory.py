"""Pricing Game Theory Model — cold-start aware A/B/C scenario generation.

Phase 2 upgrade (Week 4): When HistoricalTender data is available,
anchors A/B/C scenarios to the historical market equilibrium price
(expected_competitive_price = budget * avg_discount_rate) instead of
pure cost-plus markups.

Backward compatibility:
- market_context=None → uses original cost-plus logic exactly as before
- market_context.has_data=False → same fallback
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, asdict
from typing import Optional

from app.core.week4_pricing.price_benchmark import MarketHeatContext


# ─── Scenario output dataclass ─────────────────────────────────────────────────

@dataclass
class PriceScenario:
    """Single pricing scenario output."""
    scenario: str           # 'aggressive' | 'balanced' | 'conservative'
    price: Decimal
    label: str
    win_prob: Decimal
    profit: Decimal
    expected_value: Decimal
    risk_level: str         # 'low' | 'medium' | 'high'
    is_recommended: bool = False


# ─── Game Theory Model ────────────────────────────────────────────────────────


class PricingGameTheoryModel:
    """
    博弈定价模型（冷启动版 + 历史市场均衡增强）。

    历史数据 >= 1 条且 market_context.has_data=True 时，
    用历史均衡价（expected_competitive_price）锚定三档报价区间。

    历史数据不足时，降级为规则成本加成：
    - 激进：成本+3%
    - 平衡：成本+8%
    - 保守：成本+15%

    核心逻辑：
    1. 价格分计算（最低价满分法）：假设最低竞争对手报预算*85%
    2. 技术商务综合分 = 技术分*(1-价格分权重-0.3) + 商务分*0.3 + 价格分*价格分权重
    3. 得分→概率映射：>=90分→85%, >=80→65%, >=70→40%, <70→15%
    4. 有关系加成：relationship_index>=80 保底75%概率
    5. 期望收益 = 利润 * 中标概率
    """

    ASSUMED_LOWEST_COMPETITOR_RATIO = Decimal('0.85')  # 假设最低竞争对手报85%预算

    # ── Cold-start cost-plus markups (unchanged fallback) ─────────────────
    COLDSTART_AGGRESSIVE_MARKUP = Decimal('1.03')   # 成本+3%
    COLDSTART_BALANCED_MARKUP = Decimal('1.08')    # 成本+8%
    COLDSTART_CONSERVATIVE_MARKUP = Decimal('1.15') # 成本+15%

    def __init__(
        self,
        cost: Decimal,
        budget: Decimal,
        price_score_weight: Decimal = Decimal('0.3'),
        relationship_index: int = 0,
        tech_quality_score: Decimal = Decimal('75'),
        # ── Phase 2: market context (optional, backward compatible) ──────────
        market_context: Optional[MarketHeatContext] = None,
    ):
        if cost <= 0:
            raise ValueError(f"cost must be positive, got {cost}")
        if budget <= 0:
            raise ValueError(f"budget must be positive, got {budget}")

        self.cost = cost
        self.budget = budget
        self.price_score_weight = price_score_weight
        self.relationship_index = relationship_index
        self.tech_quality_score = tech_quality_score
        self.market_context = market_context

    # ── Convenience: build from raw values ─────────────────────────────────

    @classmethod
    def from_raw(
        cls,
        cost: float,
        budget: float,
        price_score_weight: float = 0.3,
        relationship_index: int = 0,
        tech_quality_score: float = 75.0,
        market_context: Optional[MarketHeatContext] = None,
    ) -> "PricingGameTheoryModel":
        """Factory for call sites that have float inputs."""
        return cls(
            cost=Decimal(str(cost)),
            budget=Decimal(str(budget)),
            price_score_weight=Decimal(str(price_score_weight)),
            relationship_index=relationship_index,
            tech_quality_score=Decimal(str(tech_quality_score)),
            market_context=market_context,
        )

    # ── Win probability calculation ────────────────────────────────────────

    def calculate_win_probability(self, proposed_price: Decimal) -> dict:
        """计算特定报价的中标概率和期望收益。"""
        # Guard: zero/negative price
        if proposed_price <= 0:
            return self._zero_result(proposed_price)

        # Price score (lowest-price-wins scoring)
        assumed_lowest = self.budget * self.ASSUMED_LOWEST_COMPETITOR_RATIO
        price_score = Decimal('100') if proposed_price <= assumed_lowest else (
            (assumed_lowest / proposed_price) * 100
        )

        # Combined technical + business + price score
        business_score = Decimal('90') if self.relationship_index >= 50 else Decimal('75')
        non_price_weight = Decimal('1') - self.price_score_weight - Decimal('0.3')

        total_score = (
            self.tech_quality_score * non_price_weight +
            business_score * Decimal('0.3') +
            price_score * self.price_score_weight
        )

        # Score → probability mapping
        win_prob = self._score_to_prob(total_score)

        # Relationship bonus: >=80 relationship_index → floor 75%
        if self.relationship_index >= 80:
            win_prob = max(win_prob, Decimal('0.75'))

        profit = proposed_price - self.cost
        profit_margin = (
            (profit / proposed_price).quantize(Decimal('0.0001'))
            if proposed_price > 0 else Decimal('0')
        )

        return {
            'proposed_price': proposed_price,
            'price_score': price_score.quantize(Decimal('0.01')),
            'total_score': total_score.quantize(Decimal('0.01')),
            'win_probability': win_prob,
            'expected_profit': (profit * win_prob).quantize(Decimal('0.01')),
            'profit_margin': profit_margin,
        }

    def _zero_result(self, price: Decimal) -> dict:
        """Zero-price guard result."""
        return {
            'proposed_price': price,
            'price_score': Decimal('0'),
            'total_score': Decimal('0'),
            'win_probability': Decimal('0'),
            'expected_profit': Decimal('0'),
            'profit_margin': Decimal('0'),
        }

    def _score_to_prob(self, score: Decimal) -> Decimal:
        """Score → win probability (piecewise linear)."""
        if score >= 90:
            return Decimal('0.85')
        if score >= 80:
            return Decimal('0.65')
        if score >= 70:
            return Decimal('0.40')
        return Decimal('0.15')

    # ── Scenario generation (Phase 2 upgrade) ──────────────────────────────

    def generate_price_scenarios(self) -> list[dict]:
        """
        Generate aggressive / balanced / conservative pricing scenarios.

        When market_context.is_available (historical data exists):
          Anchors scenarios to expected_competitive_price instead of cost-plus.

        When market_context is None or has no data:
          Falls back to the original cost-plus markups (backward compatible).

        Returns:
            list of dicts with keys: scenario, price, label, win_prob, profit,
            expected_value, risk_level, is_recommended
        """
        use_historical = (
            self.market_context is not None
            and self.market_context.has_data
            and self.market_context.expected_competitive_price is not None
        )

        if use_historical:
            scenarios = self._generate_historical_scenarios()
        else:
            scenarios = self._generate_coldstart_scenarios()

        # Business rule override: default to conservative recommendation
        for s in scenarios:
            s['is_recommended'] = s['scenario'] == 'conservative'

        return scenarios

    def _generate_historical_scenarios(self) -> list[dict]:
        """
        Phase 2: Historical market equilibrium pricing.

        expected_competitive_price = budget * avg_discount_rate
        This is the weighted-average winning price for similar tenders.

        Three tiers relative to equilibrium:
        - AGGRESSIVE:   equilibrium * 0.96  (slight discount to win decisively)
        - BALANCED:     equilibrium * 1.00  (at market — highest EV if competitive)
        - CONSERVATIVE: equilibrium * 1.06  (slight premium for margin safety)

        Each tier still validated against cost (can't go below cost+1%).
        """
        eq_price = self.market_context.expected_competitive_price  # Decimal, or None
        assert eq_price is not None, "expected_competitive_price must be set when has_data=True"

        # Convert to Decimal if needed (comes as Decimal from cache)
        if not isinstance(eq_price, Decimal):
            eq_price = Decimal(str(eq_price))

        # Scale to this project's budget scale
        # eq_price is stored as the discount rate (winning_price/budget) → multiply by budget
        equilibrium = (eq_price * self.budget).quantize(Decimal('0.01'))

        tier_configs = [
            # (price relative to equilibrium, label, scenario_key)
            (Decimal('0.96'), '激进策略（市场均衡价×0.96）', 'aggressive'),
            (Decimal('1.00'), '平衡策略（市场均衡价）', 'balanced'),
            (Decimal('1.06'), '保守策略（市场均衡价×1.06）', 'conservative'),
        ]

        scenarios = []
        for multiplier, label, scenario_key in tier_configs:
            raw_price = equilibrium * multiplier

            # Safety floor: never price below cost+1% (loss pricing guard)
            floor_price = (self.cost * Decimal('1.01')).quantize(Decimal('0.01'))
            price = max(raw_price, floor_price)

            result = self.calculate_win_probability(price)
            win_prob = result['win_probability']
            profit = price - self.cost

            risk = 'low' if win_prob > Decimal('0.7') else ('medium' if win_prob > Decimal('0.4') else 'high')

            scenarios.append({
                'scenario': scenario_key,
                'price': price,
                'label': label,
                'win_prob': win_prob,
                'profit': profit.quantize(Decimal('0.01')),
                'expected_value': result['expected_profit'],
                'risk_level': risk,
            })

        return scenarios

    def _generate_coldstart_scenarios(self) -> list[dict]:
        """
        Cold-start fallback: cost-plus markups (original behavior).

        Aggressive: cost * 1.03
        Balanced:   cost * 1.08
        Conservative: cost * 1.15
        """
        tier_configs = [
            (self.COLDSTART_AGGRESSIVE_MARKUP, '激进策略（成本+3%）', 'aggressive'),
            (self.COLDSTART_BALANCED_MARKUP, '平衡策略（成本+8%）', 'balanced'),
            (self.COLDSTART_CONSERVATIVE_MARKUP, '保守策略（成本+15%）', 'conservative'),
        ]

        scenarios = []
        for markup, label, scenario_key in tier_configs:
            price = (self.cost * markup).quantize(Decimal('0.01'))
            result = self.calculate_win_probability(price)
            win_prob = result['win_probability']

            risk = 'low' if win_prob > Decimal('0.7') else ('medium' if win_prob > Decimal('0.4') else 'high')

            scenarios.append({
                'scenario': scenario_key,
                'price': price,
                'label': label,
                'win_prob': win_prob,
                'profit': (price - self.cost).quantize(Decimal('0.01')),
                'expected_value': result['expected_profit'],
                'risk_level': risk,
            })

        return scenarios
