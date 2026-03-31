"""Week 2 Evaluation Schemas - Pydantic models for OwnerProfile and CostEstimator."""
from pydantic import BaseModel
from typing import Optional, Any
from app.models.enums import RelationshipLevel, CostConfidence


class OwnerProfileResult(BaseModel):
    """Result of owner profile lookup."""

    owner_name: str
    region: Optional[str] = None
    relationship_level: RelationshipLevel
    cooperation_count: int
    preferred_styles: Optional[dict[str, Any]] = None
    is_new_owner: bool


class CostEstimateResult(BaseModel):
    """Result of heuristic cost estimation."""

    estimated_cost: float
    cost_range_low: float
    cost_range_high: float
    confidence: CostConfidence
