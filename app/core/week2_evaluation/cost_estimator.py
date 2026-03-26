"""Heuristic Cost Estimator - Week 2 Evaluation.

Rough cost estimation (pre-actuarial, for early-stage decision support).
Week 4 will have the refined pricing model.
"""
from app.models.enums import CostConfidence
from app.schemas.week2 import CostEstimateResult

BASE_COST_PER_STAFF_PER_MONTH = 8000.0  # CNY
SPECIAL_REQUIREMENTS_OVERHEAD = 0.15  # 15%


class CostEstimator:
    """Heuristic cost estimator based on project scale parameters."""

    def estimate(
        self,
        estimated_staff_count: int | None,
        service_months: int | None,
        required_deposit: float | None,
        has_special_requirements: bool | None,
    ) -> CostEstimateResult:
        """
        Estimate project cost range based on scale parameters.

        Args:
            estimated_staff_count: Expected number of staff for the project
            service_months: Duration of service in months
            required_deposit: Mandatory deposit amount (保证金)
            has_special_requirements: Whether special requirements add overhead

        Returns:
            CostEstimateResult with estimated_cost, range, and confidence level
        """
        # Count numeric fields that are present (None = missing, 0 is a valid value)
        fields_present = sum(
            1
            for v in [estimated_staff_count, service_months, required_deposit]
            if v is not None
        )
        # has_special_requirements only counts toward HIGH when True (adds overhead)
        if has_special_requirements is True:
            fields_present += 1

        if fields_present >= 4:
            confidence = CostConfidence.HIGH
        elif fields_present >= 2:
            confidence = CostConfidence.MEDIUM
        else:
            confidence = CostConfidence.LOW

        # Heuristic calculation
        staff = estimated_staff_count if estimated_staff_count else 0
        months = service_months if service_months else 0
        deposit = required_deposit if required_deposit else 0.0

        subtotal = staff * months * BASE_COST_PER_STAFF_PER_MONTH
        total = subtotal + deposit

        if has_special_requirements:
            total_with_overhead = total * (1 + SPECIAL_REQUIREMENTS_OVERHEAD)
        else:
            total_with_overhead = total

        cost_range_low = total_with_overhead * 0.90
        cost_range_high = total_with_overhead * 1.15

        return CostEstimateResult(
            estimated_cost=total_with_overhead,
            cost_range_low=round(cost_range_low, 2),
            cost_range_high=round(cost_range_high, 2),
            confidence=confidence,
        )
