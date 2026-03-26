from pydantic import BaseModel
from typing import Optional, Any
from app.models.enums import Recommendation, RiskLevel, CostConfidence, TimeUrgencyLevel

# Request
class EvaluationGenerateRequest(BaseModel):
    estimated_staff_count: Optional[int] = None
    service_months: Optional[int] = None
    required_deposit: Optional[float] = None
    has_special_requirements: Optional[bool] = None

# Response (nested sections)
class QualificationSection(BaseModel):
    qualification_match_score: int
    is_qualification_pass: bool
    missing_mandatory_certs: list
    missing_optional_certs: list
    matched_certs: list

class TimeSection(BaseModel):
    days_until_bid_open: int
    time_urgency_level: str
    is_time_sufficient: bool

class OwnerSection(BaseModel):
    owner_profile_id: Optional[int]
    relationship_index: int
    is_new_owner: bool

class CostSection(BaseModel):
    estimated_cost: float
    suggested_price_range_low: float
    suggested_price_range_high: float
    cost_estimate_confidence: str

class ProbabilitySection(BaseModel):
    overall_win_probability: float

class RecommendationSection(BaseModel):
    recommendation: str
    recommendation_reason: str

class RisksSection(BaseModel):
    fatal_risks: list
    warning_risks: list
    risk_level: str

class EvaluationReportResponse(BaseModel):
    report_id: int
    qualification: QualificationSection
    time: TimeSection
    owner: OwnerSection
    cost: CostSection
    probability: ProbabilitySection
    recommendation: RecommendationSection
    risks: RisksSection
