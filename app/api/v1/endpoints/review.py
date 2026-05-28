"""Week 6 Review API endpoints — bid outcomes, review analysis, rebid detection, and draft revival."""
from datetime import datetime, timedelta, timezone, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text

from app.dependencies import get_db, get_current_user
from app.core.security import User
from app.models.project import Project
from app.models.formal_review import AbandonedDraft
from app.models.review import BidOutcome, WinningDNA, DisqualificationTrap, DraftRevival, KnowledgeEvolutionLog
from app.models.knowledge_chunk import KnowledgeChunk
from app.core.week6_review.review_engine import BidReviewEngine
from app.core.week6_review.revival_engine import DraftRevivalEngine
from app.schemas.week6 import (
    BidOutcomeRecordRequest,
    BidOutcomeResponse,
    ReviewAnalysisResponse,
    ReviewConfirmRequest,
    RebidAlertResponse,
    DraftRevivalResponse,
    KnowledgeEvolutionReportResponse,
)
from app.schemas.common import ResponseWrapper


router = APIRouter(prefix="/api/v1", tags=["review"])


# ─── Helpers ────────────────────────────────────────────────────────────────


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


# ─── 1. POST /projects/{project_id}/outcomes/record ─────────────────────────

@router.post("/projects/{project_id}/outcomes/record")
def record_outcome(
    project_id: int,
    data: BidOutcomeRecordRequest,
    db: Session = Depends(get_db),
):
    """
    Record a bid outcome and trigger BidReviewEngine auto-analysis.

    Returns BidOutcomeResponse via ResponseWrapper.
    """
    _get_project_or_404(db, project_id)

    engine = BidReviewEngine(db, project_id)

    # Determine is_win based on outcome_status
    is_win = data.outcome_status == "win"
    feedback = data.disqualification_reason or ""

    # Map request to engine's log_outcome signature
    result = engine.log_outcome(
        is_win=is_win,
        competitor_price=data.winning_price,
        feedback=feedback,
        outcome_status=data.outcome_status,
        disqualification_type=data.disqualification_type,
    )

    # Fetch the created bid_outcome record
    outcome = (
        db.query(BidOutcome)
        .filter(BidOutcome.project_id == project_id)
        .order_by(desc(BidOutcome.id))
        .first()
    )

    return ResponseWrapper(data=BidOutcomeResponse.model_validate(outcome))


# ─── 2. GET /projects/{project_id}/review-analysis ──────────────────────────

@router.get("/projects/{project_id}/review-analysis")
def get_review_analysis(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Get auto-analysis result for a project.

    Returns ReviewAnalysisResponse or 404 if no outcome found.
    """
    _get_project_or_404(db, project_id)

    # Query for the newest outcome
    outcome = (
        db.query(BidOutcome)
        .filter(BidOutcome.project_id == project_id)
        .order_by(desc(BidOutcome.id))
        .first()
    )

    if not outcome:
        raise HTTPException(status_code=404, detail="No bid outcome found for this project")

    engine = BidReviewEngine(db, project_id)
    analysis = engine.get_analysis()

    # Query for DNA extracted
    dna_ids = (
        db.query(WinningDNA.id)
        .filter(WinningDNA.project_id == project_id)
        .all()
    )
    dna_extracted = [dna.id for dna in dna_ids]

    return ReviewAnalysisResponse(
        project_id=project_id,
        outcome_status=outcome.outcome_status,
        analysis_type=outcome.outcome_status,
        detected_trap=None,
        is_manual_error=outcome.is_manual_error,
        dna_extracted=dna_extracted if dna_extracted else None,
        price_strategy=None,
        suggestions=[],
    )


# ─── 3. POST /projects/{project_id}/review-analysis/confirm ────────────────

@router.post("/projects/{project_id}/review-analysis/confirm")
def confirm_review_analysis(
    project_id: int,
    data: ReviewConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Confirm review analysis and trigger knowledge evolution.

    Updates BidOutcome with reviewed_by, reviewed_at, review_notes, review_analysis.
    """
    _get_project_or_404(db, project_id)

    # Find the bid_outcome
    outcome = (
        db.query(BidOutcome)
        .filter(BidOutcome.project_id == project_id)
        .order_by(desc(BidOutcome.id))
        .first()
    )

    if not outcome:
        raise HTTPException(status_code=404, detail="No bid outcome found for this project")

    # Update outcome
    outcome.reviewed_by = 1  # TODO: from auth context
    outcome.reviewed_at = datetime.now(timezone.utc)
    outcome.review_notes = data.manual_notes
    outcome.review_analysis = data.confirmed_analysis

    db.commit()
    db.refresh(outcome)

    return ResponseWrapper(data=BidOutcomeResponse.model_validate(outcome))


# ─── 4. GET /projects/{project_id}/rebid-alert ───────────────────────────────

@router.get("/projects/{project_id}/rebid-alert")
def get_rebid_alert(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Detect if a new project is a rebid of a historical project.

    Uses BidReviewEngine.detect_similar_rebid() to find historical projects
    with same owner_unit and bid_open_date within 12 months.
    """
    _get_project_or_404(db, project_id)

    engine = BidReviewEngine(db, project_id)
    result = engine.detect_similar_rebid(project_id)

    return RebidAlertResponse(**result)


# ─── 5. POST /revivals/{abandoned_draft_id}/revive-to/{new_project_id} ─────

@router.post("/revivals/{abandoned_draft_id}/revive-to/{new_project_id}")
def revive_draft(
    abandoned_draft_id: int,
    new_project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute draft revival — revive an abandoned draft for a new project.

    CRITICAL: Catches ValueError from engine and returns 400.
    """
    _get_project_or_404(db, new_project_id)

    engine = DraftRevivalEngine(db, abandoned_draft_id)

    try:
        result = engine.revive_draft(user_id=current_user.id, reason="rebid")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch the created draft_revival record
    revival = (
        db.query(DraftRevival)
        .filter(DraftRevival.abandoned_draft_id == abandoned_draft_id)
        .order_by(desc(DraftRevival.id))
        .first()
    )

    return DraftRevivalResponse.model_validate(revival)


# ─── 6. GET /knowledge-base/evolution-report ───────────────────────────────

@router.get("/knowledge-base/evolution-report")
def get_evolution_report(
    db: Session = Depends(get_db),
):
    """
    Return knowledge base stats for dashboard.

    Queries:
    - total_chunks: COUNT(*) from knowledge_chunks
    - deprecated_this_month: deprecated chunks created in last 30 days
    - weighted_by_wins: WinningDNA records in last 30 days
    - new_traps_added: DisqualificationTrap records in last 30 days
    - avg_quality_score_trend: compare last 30 days vs previous 30 days
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    # total_chunks
    total_chunks = db.query(func.count(KnowledgeChunk.id)).scalar() or 0

    # deprecated_this_month
    deprecated_this_month = (
        db.query(func.count(KnowledgeChunk.id))
        .filter(
            KnowledgeChunk.is_deprecated == True,
            KnowledgeChunk.created_at >= thirty_days_ago,
        )
        .scalar()
    ) or 0

    # weighted_by_wins (WinningDNA records in last 30 days)
    weighted_by_wins = (
        db.query(func.count(WinningDNA.id))
        .filter(WinningDNA.extracted_at >= thirty_days_ago)
        .scalar()
    ) or 0

    # new_traps_added (DisqualificationTrap records in last 30 days)
    new_traps_added = (
        db.query(func.count(DisqualificationTrap.id))
        .filter(DisqualificationTrap.created_at >= thirty_days_ago)
        .scalar()
    ) or 0

    # avg_quality_score_trend: compare avg quality_score last 30 days vs previous 30 days
    # Get chunks from last 30 days
    recent_chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.created_at >= thirty_days_ago)
        .all()
    )
    previous_chunks = (
        db.query(KnowledgeChunk)
        .filter(
            KnowledgeChunk.created_at >= sixty_days_ago,
            KnowledgeChunk.created_at < thirty_days_ago,
        )
        .all()
    )

    def avg_quality(chunks):
        scores = []
        for chunk in chunks:
            if chunk.chunk_metadata and isinstance(chunk.chunk_metadata, dict):
                score = chunk.chunk_metadata.get("quality_score")
                if score is not None:
                    scores.append(float(score))
        return sum(scores) / len(scores) if scores else 0.0

    recent_avg = avg_quality(recent_chunks)
    previous_avg = avg_quality(previous_chunks)

    if recent_avg > previous_avg + 2:
        trend = "up"
    elif recent_avg < previous_avg - 2:
        trend = "down"
    else:
        trend = "stable"

    return KnowledgeEvolutionReportResponse(
        total_chunks=total_chunks,
        deprecated_this_month=deprecated_this_month,
        weighted_by_wins=weighted_by_wins,
        new_traps_added=new_traps_added,
        avg_quality_score_trend=trend,
    )
