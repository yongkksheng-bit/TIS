"""Pricing Game Theory Model — cold-start aware A/B/C scenario generation."""
from decimal import Decimal
from dataclasses import dataclass, asdict


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


class PricingGameTheoryModel:
    """
    博弈定价模型（冷启动版）。
    历史数据 >= 5 条时增强，< 5 条时降级为规则启发式。

    核心逻辑：
    1. 价格分计算（最低价满分法）：假设最低竞争对手报预算*85%
    2. 技术商务综合分 = 技术分*(1-价格分权重-0.3) + 商务分*0.3 + 价格分*价格分权重
    3. 得分→概率映射：>=90分→85%, >=80→65%, >=70→40%, <70→15%
    4. 有关系加成：relationship_index>=80 保底75%概率
    5. 期望收益 = 利润 * 中标概率
    """

    ASSUMED_LOWEST_COMPETITOR_RATIO = Decimal('0.85')  # 假设最低竞争对手报85%预算

    def __init__(
        self,
        cost: Decimal,
        budget: Decimal,
        price_score_weight: Decimal = Decimal('0.3'),
        relationship_index: int = 0,
        tech_quality_score: Decimal = Decimal('75'),
    ):
        self.cost = cost
        self.budget = budget
        self.price_score_weight = price_score_weight
        self.relationship_index = relationship_index
        self.tech_quality_score = tech_quality_score

    def calculate_win_probability(self, proposed_price: Decimal) -> dict:
        """计算特定报价的中标概率和期望收益。"""
        # 1. 价格分（最低价满分法）
        assumed_lowest = self.budget * self.ASSUMED_LOWEST_COMPETITOR_RATIO
        if proposed_price <= assumed_lowest:
            price_score = Decimal('100')
        else:
            price_score = (assumed_lowest / proposed_price) * 100

        # 2. 技术商务综合分
        business_score = Decimal('90') if self.relationship_index >= 50 else Decimal('75')
        non_price_weight = Decimal('1') - self.price_score_weight - Decimal('0.3')

        total_score = (
            self.tech_quality_score * non_price_weight +
            business_score * Decimal('0.3') +
            price_score * self.price_score_weight
        )

        # 3. 概率映射
        win_prob = self._score_to_prob(total_score)

        # 4. 关系加成（有关系项目至少75%）
        if self.relationship_index >= 80:
            win_prob = max(win_prob, Decimal('0.75'))

        profit = proposed_price - self.cost
        return {
            'proposed_price': proposed_price,
            'price_score': price_score.quantize(Decimal('0.01')),
            'total_score': total_score.quantize(Decimal('0.01')),
            'win_probability': win_prob,
            'expected_profit': (profit * win_prob).quantize(Decimal('0.01')),
            'profit_margin': (profit / proposed_price).quantize(Decimal('0.0001')),
        }

    def _score_to_prob(self, score: Decimal) -> Decimal:
        """得分 → 中标概率（Sigmoid线性分段）。"""
        if score >= 90:
            return Decimal('0.85')
        if score >= 80:
            return Decimal('0.65')
        if score >= 70:
            return Decimal('0.40')
        return Decimal('0.15')

    def generate_price_scenarios(self) -> list[dict]:
        """生成激进/平衡/保守三种价格场景。"""
        scenarios = []
        for markup, label, scenario_key in [
            (Decimal('1.03'), '激进策略（成本+3%）', 'aggressive'),
            (Decimal('1.08'), '平衡策略（成本+8%）', 'balanced'),
            (Decimal('1.15'), '保守策略（成本+15%）', 'conservative'),
        ]:
            price = (self.cost * markup).quantize(Decimal('0.01'))
            result = self.calculate_win_probability(price)
            win_prob = result['win_probability']

            if win_prob > Decimal('0.7'):
                risk = 'low'
            elif win_prob > Decimal('0.4'):
                risk = 'medium'
            else:
                risk = 'high'

            scenarios.append({
                'scenario': scenario_key,
                'price': price,
                'label': label,
                'win_prob': win_prob,
                'profit': (price - self.cost).quantize(Decimal('0.01')),
                'expected_value': result['expected_profit'],
                'risk_level': risk,
            })

        # 推荐期望收益最高
        best = max(scenarios, key=lambda x: x['expected_value'])
        best['is_recommended'] = True

        return scenarios
