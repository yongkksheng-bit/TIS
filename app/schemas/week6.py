"""Week 6 Pydantic schemas for review and knowledge evolution."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import date, datetime


class BidOutcomeRecordRequest(BaseModel):
    """Request schema for recording a bid outcome."""
    outcome_status: Literal['win', 'lose', 'disqualified', 'abandoned', 'withdrawn']
    outcome_date: date
    final_bid_price: float
    winning_price: Optional[float] = None
    winning_unit: Optional[str] = None
    our_price_rank: Optional[int] = None
    disqualification_reason: Optional[str] = None
    disqualification_type: Optional[Literal['fatal_formal', 'fatal_qualification', 'fatal_price', 'tech_deficiency', 'price_uncompetitive']] = None
    extract_dna: bool = True  # whether to extract winning DNA
    update_traps: bool = True  # whether to update trap library


class BidOutcomeResponse(BaseModel):
    """Response schema for bid outcome."""
    id: int
    project_id: int
    outcome_status: str
    outcome_date: date
    final_bid_price: float
    winning_price: Optional[float] = None
    winning_unit: Optional[str] = None
    our_price_rank: Optional[int] = None
    disqualification_reason: Optional[str] = None
    disqualification_type: Optional[str] = None
    related_review_item_id: Optional[int] = None
    is_manual_error: bool
    review_analysis: Optional[dict] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReviewAnalysisResponse(BaseModel):
    """Response schema for review analysis."""
    project_id: int
    outcome_status: str
    analysis_type: str  # win/lose/disqualification
    detected_trap: Optional[str] = None
    is_manual_error: bool
    dna_extracted: Optional[list[int]] = None  # list of winning_dna IDs
    price_strategy: Optional[dict] = None
    suggestions: list[str]


class ReviewConfirmRequest(BaseModel):
    """Request schema for confirming a review analysis."""
    confirmed_analysis: dict
    manual_notes: str
    extract_dna: bool = True
    update_traps: bool = True


class RebidAlertResponse(BaseModel):
    """Response schema for rebid alert."""
    is_rebid: bool
    historical_project_id: Optional[int] = None
    historical_outcome: Optional[str] = None
    similarity_score: Optional[float] = None
    alert_level: Optional[str] = None  # high/medium/low
    warnings: list[str]
    revivable_drafts: Optional[list[dict]] = None


class DraftRevivalResponse(BaseModel):
    """Response schema for draft revival."""
    id: int
    abandoned_draft_id: int
    new_project_id: int
    revival_type: str
    revived_content: Optional[dict] = None
    adaptation_notes: Optional[str] = None
    revived_by: Optional[int] = None
    revived_at: datetime
    is_successful: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)


class KnowledgeEvolutionReportResponse(BaseModel):
    """Response schema for knowledge evolution report."""
    total_chunks: int
    deprecated_this_month: int
    weighted_by_wins: int
    new_traps_added: int
    avg_quality_score_trend: str  # up/down/stable
