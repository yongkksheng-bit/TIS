"""Tests for CostEstimator - TDD."""
import pytest
from app.core.week2_evaluation.cost_estimator import CostEstimator
from app.models.enums import CostConfidence


class TestCostEstimator:
    """TDD tests for CostEstimator."""

    def test_complete_data_returns_high_confidence(self):
        """All 4 fields present → HIGH confidence."""
        estimator = CostEstimator()
        result = estimator.estimate(
            estimated_staff_count=10,
            service_months=12,
            required_deposit=50000.0,
            has_special_requirements=True,
        )
        assert result.confidence == CostConfidence.HIGH

    def test_partial_data_returns_medium_confidence(self):
        """2-3 fields present → MEDIUM confidence."""
        estimator = CostEstimator()
        # 3 fields present (no has_special_requirements)
        result = estimator.estimate(
            estimated_staff_count=10,
            service_months=12,
            required_deposit=50000.0,
            has_special_requirements=None,
        )
        assert result.confidence == CostConfidence.MEDIUM

        # 2 fields present
        result2 = estimator.estimate(
            estimated_staff_count=10,
            service_months=0,
            required_deposit=50000.0,
            has_special_requirements=None,
        )
        assert result2.confidence == CostConfidence.MEDIUM

    def test_sparse_data_returns_low_confidence(self):
        """Fewer than 2 fields → LOW confidence."""
        estimator = CostEstimator()
        result = estimator.estimate(
            estimated_staff_count=10,
            service_months=None,
            required_deposit=None,
            has_special_requirements=None,
        )
        assert result.confidence == CostConfidence.LOW

        # Only 1 field
        result2 = estimator.estimate(
            estimated_staff_count=10,
            service_months=None,
            required_deposit=None,
            has_special_requirements=False,
        )
        assert result2.confidence == CostConfidence.LOW

    def test_cost_range_with_special_requirements(self):
        """Special requirements add 15% overhead."""
        estimator = CostEstimator()
        result = estimator.estimate(
            estimated_staff_count=10,
            service_months=12,
            required_deposit=0.0,
            has_special_requirements=True,
        )
        # 10 * 12 * 8000 = 960000, + 15% = 1,104,000
        assert result.estimated_cost == 1_104_000.0
        assert result.cost_range_low == 993_600.0
        assert result.cost_range_high == 1_269_600.0

    def test_cost_range_without_special_requirements(self):
        """No overhead when special requirements are absent."""
        estimator = CostEstimator()
        result = estimator.estimate(
            estimated_staff_count=10,
            service_months=12,
            required_deposit=0.0,
            has_special_requirements=False,
        )
        # 10 * 12 * 8000 = 960000, no overhead
        assert result.estimated_cost == 960_000.0
        assert result.cost_range_low == 864_000.0
        assert result.cost_range_high == 1_104_000.0

    def test_zero_deposit_still_works(self):
        """Edge case: required_deposit=0 should not break calculation."""
        estimator = CostEstimator()
        result = estimator.estimate(
            estimated_staff_count=5,
            service_months=6,
            required_deposit=0,
            has_special_requirements=None,
        )
        # 5 * 6 * 8000 = 240000
        assert result.estimated_cost == 240_000.0
        # 3 numeric fields present, special is None → MEDIUM (not HIGH without special=True)
        assert result.confidence == CostConfidence.MEDIUM

    def test_zero_staff_count_treated_as_zero(self):
        """estimated_staff_count=0 should be treated as 0, not missing."""
        estimator = CostEstimator()
        result = estimator.estimate(
            estimated_staff_count=0,
            service_months=12,
            required_deposit=100000.0,
            has_special_requirements=False,
        )
        # 0 * 12 * 8000 + 100000 = 100000
        assert result.estimated_cost == 100_000.0
        # 3 fields present (counted as present since 0 is a value, not None)
        assert result.confidence == CostConfidence.MEDIUM
