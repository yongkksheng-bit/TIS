"""Pricing Intercept Rules — hard constraints for cost/price validation."""
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class InterceptResult:
    """Result of an intercept rule check."""
    level: str  # 'ok' | 'warning' | 'error' | 'over_limit'
    message: str = ""
    requires_confirmation: bool = False
    requires_reason: bool = False
    deviation_pct: Decimal = Decimal('0')


class PricingInterceptRules:
    """
    定价拦截规则（硬性约束）。

    规则1：成本倒挂拦截
      → total_cost > budget_limit * 0.95 → warning（不阻止，继续）

    规则2：亏损定价拦截
      → boss_final < total_cost * 1.01 → error（阻止提交）

    规则3：超限价强制确认
      → boss_final > budget_limit → over_limit（阻止，需二次确认）

    规则4：差异>5%强制填原因
      → |boss_final - system_optimal| / system_optimal > 0.05 → requires_reason
    """

    def check_cost_vs_budget(
        self, total_cost: Decimal, budget_limit: Decimal
    ) -> InterceptResult:
        """规则1：成本接近/超过限价 → 成本倒挂警告."""
        if total_cost > budget_limit * Decimal('0.95'):
            return InterceptResult(
                level='warning',
                message=f"成本{total_cost}接近限价{budget_limit}，利润空间极小，建议确认是否继续",
            )
        return InterceptResult(level='ok')

    def check_final_price(
        self,
        final_price: Decimal,
        total_cost: Decimal,
        budget_limit: Decimal | None = None,
        system_optimal: Decimal | None = None,
    ) -> InterceptResult:
        """
        规则2+3+4：亏损/超限/差异过大检查.

        Returns InterceptResult with:
          - level: 'ok' | 'error' | 'over_limit' | 'warning'
          - requires_confirmation: bool (for over_limit)
          - requires_reason: bool (for deviation > 5%)
        """
        # 规则2：亏损定价（利润<1%）
        if final_price < total_cost * Decimal('1.01'):
            return InterceptResult(
                level='error',
                message="亏损定价不可接受（利润率需≥1%）",
            )

        # 规则3：超限价
        if budget_limit and final_price > budget_limit:
            return InterceptResult(
                level='over_limit',
                message=f"报价{final_price}超过限价{budget_limit}，可能直接废标",
                requires_confirmation=True,
            )

        # 规则4：差异>5%
        if system_optimal:
            deviation = abs(final_price - system_optimal) / system_optimal
            if deviation > Decimal('0.05'):
                return InterceptResult(
                    level='warning',
                    message=f"与系统推荐价差异{deviation:.1%}，需填写原因",
                    requires_reason=True,
                    deviation_pct=deviation,
                )

        return InterceptResult(level='ok')

    def check_deviation(
        self, boss_final: Decimal, system_optimal: Decimal
    ) -> InterceptResult:
        """规则4：单独检查与系统推荐价的偏差."""
        deviation = abs(boss_final - system_optimal) / system_optimal
        return InterceptResult(
            level='warning' if deviation > Decimal('0.05') else 'ok',
            requires_reason=deviation > Decimal('0.05'),
            deviation_pct=deviation,
        )
