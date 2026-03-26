"""BidEvaluationEngine - Week 2 Orchestrator.

Orchestrates all Week 2 evaluation components into a single comprehensive report.
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.core.week2_evaluation.qualification_matcher import QualificationMatcher
from app.core.week2_evaluation.time_evaluator import TimeEvaluator
from app.core.week2_evaluation.owner_service import OwnerProfileService
from app.core.week2_evaluation.cost_estimator import CostEstimator
from app.core.week2_evaluation.win_probability_calculator import WinProbabilityCalculator
from app.models.evaluation import BidEvaluationReport
from app.models.enums import Recommendation, RiskLevel, TimeUrgencyLevel
from app.models.project import Project


class BidEvaluationEngine:
    """
    Orchestrator for Week 2 bid evaluation.

    Combines qualification matching, time urgency, owner profile,
    cost estimation, and win probability into a single report with recommendation.
    """

    def __init__(self, db: Session, project_id: int):
        self.db = db
        self.project_id = project_id

    def generate_report(self, user_inputs: dict | None = None) -> dict:
        """
        Generate a comprehensive bid evaluation report.

        Args:
            user_inputs: Optional dict containing project_scale data for CostEstimator:
                - estimated_staff_count: int
                - service_months: int
                - required_deposit: float
                - has_special_requirements: bool

        Returns:
            dict with all report sections:
                - report_id: int (DB primary key)
                - qualification: {...}
                - time: {...}
                - owner: {...}
                - cost: {...}
                - probability: {...}
                - recommendation: {...}
                - risks: {...}
        """
        # Get project for date and owner info
        project = self.db.get(Project, self.project_id)
        if not project:
            raise ValueError(f"Project {self.project_id} not found")

        # 1. Qualification Matcher
        qual_matcher = QualificationMatcher(self.db, self.project_id)
        qual_result = qual_matcher.exact_match_evaluation()

        # 2. Time Evaluator
        time_evaluator = TimeEvaluator()
        time_result = time_evaluator.calculate(project.bid_open_date)

        # 3. Owner Profile Service
        owner_service = OwnerProfileService(self.db)
        owner_result = owner_service.get_profile(
            owner_name=project.owner_unit,
            region=project.region
        )

        # 4. Cost Estimator
        cost_estimator = CostEstimator()
        if user_inputs:
            cost_result = cost_estimator.estimate(
                estimated_staff_count=user_inputs.get('estimated_staff_count'),
                service_months=user_inputs.get('service_months'),
                required_deposit=user_inputs.get('required_deposit'),
                has_special_requirements=user_inputs.get('has_special_requirements')
            )
        else:
            cost_result = cost_estimator.estimate(None, None, None, None)

        # 5. Win Probability Calculator
        # relationship_level may be an enum, a string ('none'/'weak'/'medium'/'strong'), or an int
        rl = owner_result.relationship_level
        if hasattr(rl, 'value'):
            # It's an enum - use .value which may be int or string
            rl_val = rl.value
            relationship_index = int(rl_val) if isinstance(rl_val, (int, str)) and str(rl_val).isnumeric() else _relationship_str_to_index(rl_val)
        elif isinstance(rl, str):
            relationship_index = _relationship_str_to_index(rl)
        else:
            relationship_index = int(rl)
        win_calculator = WinProbabilityCalculator()
        win_prob = win_calculator.calculate(
            qual_score=qual_result['qualification_match_score'],
            time_level=time_result['time_urgency_level'],
            relationship_index=relationship_index,
            competition_count=1  # Default competition count
        )

        # Build recommendation and risks
        recommendation, recommendation_reason = self._determine_recommendation(
            win_prob=win_prob,
            qual_result=qual_result,
            time_result=time_result
        )

        fatal_risks = self._collect_fatal_risks(qual_result, time_result)
        warning_risks = self._collect_warning_risks(owner_result)

        risk_level = self._determine_risk_level(fatal_risks, warning_risks)

        # Persist to database
        report = BidEvaluationReport(
            project_id=self.project_id,
            qualification_match_score=qual_result['qualification_match_score'],
            missing_mandatory_certs=qual_result['missing_mandatory_certs'],
            missing_optional_certs=qual_result['missing_optional_certs'],
            matched_certs_detail=qual_result['matched_certs'],
            days_until_bid_open=time_result['days_until_bid_open'],
            time_urgency_level=time_result['time_urgency_level'],
            is_time_sufficient=time_result['is_time_sufficient'],
            owner_profile_id=owner_result.id if hasattr(owner_result, 'id') and owner_result.id else None,
            relationship_index=relationship_index,
            is_new_owner=owner_result.is_new_owner,
            estimated_cost=cost_result.estimated_cost,
            suggested_price_range_low=cost_result.cost_range_low,
            suggested_price_range_high=cost_result.cost_range_high,
            cost_estimate_confidence=cost_result.confidence,
            overall_win_probability=win_prob,
            risk_level=risk_level,
            fatal_risks=fatal_risks,
            warning_risks=warning_risks,
            recommendation=recommendation,
            recommendation_reason=recommendation_reason,
            confirmed_by_specialist=False,
            specialist_decision=None,
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # Build return dict with all sections
        return {
            'report_id': report.id,
            'qualification': {
                'qualification_match_score': qual_result['qualification_match_score'],
                'is_qualification_pass': qual_result['is_qualification_pass'],
                'missing_mandatory_certs': qual_result['missing_mandatory_certs'],
                'missing_optional_certs': qual_result['missing_optional_certs'],
                'matched_certs': qual_result['matched_certs'],
            },
            'time': {
                'days_until_bid_open': time_result['days_until_bid_open'],
                'time_urgency_level': time_result['time_urgency_level'],
                'is_time_sufficient': time_result['is_time_sufficient'],
            },
            'owner': {
                'owner_profile_id': report.owner_profile_id,
                'relationship_index': relationship_index,
                'is_new_owner': owner_result.is_new_owner,
            },
            'cost': {
                'estimated_cost': cost_result.estimated_cost,
                'suggested_price_range_low': cost_result.cost_range_low,
                'suggested_price_range_high': cost_result.cost_range_high,
                'cost_estimate_confidence': cost_result.confidence.value if hasattr(cost_result.confidence, 'value') else cost_result.confidence,
            },
            'probability': {
                'overall_win_probability': win_prob,
            },
            'recommendation': {
                'recommendation': recommendation.value if hasattr(recommendation, 'value') else recommendation,
                'recommendation_reason': recommendation_reason,
            },
            'risks': {
                'fatal_risks': fatal_risks,
                'warning_risks': warning_risks,
                'risk_level': risk_level.value if hasattr(risk_level, 'value') else risk_level,
            },
        }

    def _determine_recommendation(
        self,
        win_prob: float,
        qual_result: dict,
        time_result: dict
    ) -> tuple:
        """
        Determine recommendation based on win probability and fatal conditions.

        Returns:
            tuple of (Recommendation enum, reason string)
        """
        # Fatal conditions
        if win_prob == 0:
            if time_result['time_urgency_level'] == 'expired':
                return (
                    Recommendation.ABANDON,
                    "Bid deadline has expired - cannot submit"
                )
            elif qual_result['qualification_match_score'] < 60:
                return (
                    Recommendation.ABANDON,
                    f"Qualification score {qual_result['qualification_match_score']} below fatal threshold (60)"
                )
            else:
                return (
                    Recommendation.ABANDON,
                    "Win probability is zero due to fatal risk factors"
                )

        # High probability - worth bidding
        if win_prob > 0.60:
            return (
                Recommendation.WORTH_BIDDING,
                f"Win probability {win_prob:.0%} indicates strong opportunity"
            )

        # Medium probability - conditional
        if 0 < win_prob <= 0.60:
            return (
                Recommendation.CONDITIONAL,
                f"Win probability {win_prob:.0%} requires further discussion and specialist review"
            )

        # Fallback
        return (
            Recommendation.CONDITIONAL,
            "Unable to determine clear recommendation"
        )

    def _collect_fatal_risks(self, qual_result: dict, time_result: dict) -> list:
        """Collect all fatal risks."""
        fatal_risks = []

        # Qualification failures
        if not qual_result['is_qualification_pass']:
            for cert in qual_result['missing_mandatory_certs']:
                reason = cert.get('reason', 'missing')
                fatal_risks.append({
                    'type': 'qualification',
                    'severity': 'fatal',
                    'cert_code': cert.get('cert_code'),
                    'reason': reason,
                    'message': f"Mandatory cert '{cert.get('cert_name', cert.get('cert_code'))}' is {reason}"
                })

        # Time expiry
        if time_result['time_urgency_level'] == 'expired':
            fatal_risks.append({
                'type': 'time',
                'severity': 'fatal',
                'reason': 'expired',
                'message': 'Bid deadline has already passed'
            })

        return fatal_risks

    def _collect_warning_risks(self, owner_result) -> list:
        """Collect all warning risks."""
        warning_risks = []

        if owner_result.is_new_owner:
            warning_risks.append({
                'type': 'owner',
                'severity': 'warning',
                'reason': 'new_owner',
                'message': 'No prior cooperation history with this owner - relationship risk'
            })

        return warning_risks

    def _determine_risk_level(self, fatal_risks: list, warning_risks: list) -> RiskLevel:
        """Determine overall risk level based on collected risks."""
        if fatal_risks:
            return RiskLevel.HIGH
        if warning_risks:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


def _relationship_str_to_index(value) -> int:
    """Convert relationship level to index (0-3)."""
    mapping = {'none': 0, 'weak': 1, 'medium': 2, 'strong': 3}
    if isinstance(value, int):
        return value
    return mapping.get(str(value).lower(), 0)
