"""Cost Estimation Engine — cold-start aware cost breakdown."""
import enum
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from app.models.pricing import PriceHistory


class CostConfidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CostEstimationEngine:
    """
    基于历史项目数据，智能测算新项目成本。
    冷启动策略：无历史数据时使用预算*75%估算。
    """

    # 行业经验比例（食材配送）
    FOOD_RATIO = Decimal('0.55')
    LABOR_RATIO = Decimal('0.25')
    LOGISTICS_RATIO = Decimal('0.12')
    MGMT_RATIO = Decimal('0.08')

    def estimate_from_history(
        self,
        project_type: str,
        region: str,
        budget: Decimal,
        db: Optional[Session] = None,
    ) -> dict:
        """
        基于历史数据估算， fallback 到预算比例。

        Returns:
            dict with keys: estimated_total, confidence, based_on, breakdown, warning(optional)
        """
        if db is not None:
            similar = self._find_similar(db, project_type, region, budget)
            if similar:
                estimated = self._weighted_average(similar, budget)
                return {
                    'estimated_total': estimated,
                    'confidence': 'medium' if len(similar) >= 3 else 'low',
                    'based_on': f"{len(similar)}个历史相似项目",
                    'breakdown': self.breakdown_cost(estimated),
                }

        # 冷启动 fallback：无历史数据
        estimated = budget * Decimal('0.75')
        return {
            'estimated_total': estimated,
            'confidence': 'low',
            'based_on': '行业经验比例（预算75%）',
            'breakdown': self.breakdown_cost(estimated),
            'warning': '无相似历史项目，建议人工仔细核算',
        }

    def breakdown_cost(self, total: Decimal) -> dict:
        """成本拆解为明细（行业经验比例）。"""
        return {
            'food_cost': (total * self.FOOD_RATIO).quantize(Decimal('0.01')),
            'labor_cost': (total * self.LABOR_RATIO).quantize(Decimal('0.01')),
            'logistics_cost': (total * self.LOGISTICS_RATIO).quantize(Decimal('0.01')),
            'management_cost': (total * self.MGMT_RATIO).quantize(Decimal('0.01')),
        }

    def _find_similar(
        self, db: Session, project_type: str, region: str, budget: Decimal, threshold: float = 0.2
    ) -> list:
        """查找历史相似项目（类型+地区+预算差异<20%）。"""
        from sqlalchemy import and_, func
        budget_float = float(budget)
        lower = budget_float * (1 - threshold)
        upper = budget_float * (1 + threshold)

        records = db.execute(
            PriceHistory.__table__.select().where(
                and_(
                    PriceHistory.project_type == project_type,
                    PriceHistory.region == region,
                    PriceHistory.budget_amount.between(lower, upper),
                )
            )
        ).fetchall()
        return records

    def _weighted_average(self, records: list, current_budget: Decimal) -> Decimal:
        """基于历史成本加权平均（通胀调整）。"""
        if not records:
            return current_budget * Decimal('0.75')

        total_weight = Decimal('0')
        weighted_sum = Decimal('0')

        for record in records:
            # weight = 1 / (1 + abs(budget - record.budget_amount) / record.budget_amount)
            diff_ratio = abs(current_budget - Decimal(str(record.budget_amount))) / Decimal(str(record.budget_amount))
            weight = Decimal('1') / (Decimal('1') + diff_ratio)
            cost = Decimal(str(record.our_cost))
            weighted_sum += cost * weight
            total_weight += weight

        if total_weight == 0:
            return current_budget * Decimal('0.75')

        avg = weighted_sum / total_weight

        # 简单通胀调整（+5%）
        adjusted = avg * Decimal('1.05')
        return adjusted.quantize(Decimal('0.01'))