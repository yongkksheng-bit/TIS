"""Formal review API endpoints — initiate, review items, status, and final document generation."""
import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.project import Project
from app.models.formal_review import FormalReviewItem, AbandonedDraft, FinalBidDocument
from app.models.pricing import PricingDecision, CostEstimate
from app.models.tech_proposal import TechProposalTask
from app.core.week5_formal_review.formal_review_engine import FormalReviewEngine
from app.core.week5_formal_review.word_generator import FinalBidWordGenerator
from app.schemas.week5 import (
    FormalReviewItemResponse,
    FormalReviewStatusResponse,
    ReviewItemConfirmRequest,
    ReviewItemCorrectRequest,
    ManualReviewItemRequest,
    FinalDocGenerateResponse,
    AbandonedDraftResponse,
)
from app.schemas.common import ResponseWrapper


router = APIRouter(prefix="/api/v1", tags=["formal_review"])


# ─── Helpers ────────────────────────────────────────────────────────────────


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


def _get_review_item_or_404(db: Session, item_id: int) -> FormalReviewItem:
    item = db.get(FormalReviewItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"FormalReviewItem {item_id} not found")
    return item


def _check_can_generate(db: Session, project_id: int):
    """
    Check if final document generation is allowed.

    Returns:
        tuple[bool, str | None]: (can_generate, blocking_reason)
    """
    items = db.query(FormalReviewItem).filter(FormalReviewItem.project_id == project_id).all()

    fatal_pending = sum(
        1 for item in items
        if item.risk_level == 'fatal' and item.specialist_status == 'pending'
    )
    warning_pending = sum(
        1 for item in items
        if item.risk_level == 'warning' and item.specialist_status == 'pending'
    )

    if fatal_pending > 0:
        return False, f"存在{fatal_pending}项致命风险未处理"
    if warning_pending > 0:
        return True, f"存在{warning_pending}项警告未确认"
    return True, None


# ─── 1. POST /projects/{project_id}/formal-review/initiate ────────────────

@router.post("/projects/{project_id}/formal-review/initiate")
def initiate_formal_review(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Initiate formal review by generating a checklist via FormalReviewEngine.

    Returns total_items count and fatal_count.
    """
    _get_project_or_404(db, project_id)

    engine = FormalReviewEngine(db, project_id)
    checklist = engine.generate_review_checklist()

    fatal_count = sum(1 for item in checklist if item.get('risk_level') == 'fatal')

    return ResponseWrapper(data={
        "total_items": len(checklist),
        "fatal_count": fatal_count,
    })


# ─── 2. GET /projects/{project_id}/formal-review/items ─────────────────────

@router.get("/projects/{project_id}/formal-review/items")
def get_formal_review_items(
    project_id: int,
    status: Optional[str] = Query(None, description="Filter by specialist_status"),
    risk_level: Optional[str] = Query(None, description="Filter by risk_level"),
    db: Session = Depends(get_db),
):
    """
    Return all formal review items for a project, optionally filtered.
    """
    _get_project_or_404(db, project_id)

    query = db.query(FormalReviewItem).filter(FormalReviewItem.project_id == project_id)

    if status is not None:
        query = query.filter(FormalReviewItem.specialist_status == status)
    if risk_level is not None:
        query = query.filter(FormalReviewItem.risk_level == risk_level)

    items = query.all()
    return [FormalReviewItemResponse.model_validate(item) for item in items]


# ─── 3. GET /projects/{project_id}/formal-review/status ─────────────────────

@router.get("/projects/{project_id}/formal-review/status")
def get_formal_review_status(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Return FormalReviewStatusResponse with aggregate counts.
    """
    _get_project_or_404(db, project_id)

    items = db.query(FormalReviewItem).filter(FormalReviewItem.project_id == project_id).all()

    total_items = len(items)
    confirmed_items = sum(1 for item in items if item.specialist_status == 'confirmed')
    fatal_pending = sum(
        1 for item in items
        if item.risk_level == 'fatal' and item.specialist_status == 'pending'
    )
    warning_pending = sum(
        1 for item in items
        if item.risk_level == 'warning' and item.specialist_status == 'pending'
    )

    can_generate, blocking_reason = _check_can_generate(db, project_id)

    return FormalReviewStatusResponse(
        project_id=project_id,
        total_items=total_items,
        confirmed_items=confirmed_items,
        fatal_pending=fatal_pending,
        warning_pending=warning_pending,
        can_generate=can_generate,
        blocking_reason=blocking_reason,
    )


# ─── 4. POST /formal-review-items/{item_id}/confirm ────────────────────────

@router.post("/formal-review-items/{item_id}/confirm")
def confirm_formal_review_item(
    item_id: int,
    data: ReviewItemConfirmRequest = None,
    db: Session = Depends(get_db),
):
    """
    Mark a review item as confirmed by specialist.
    Sets specialist_status='confirmed', confirmed_by=1, confirmed_at=utcnow.
    """
    item = _get_review_item_or_404(db, item_id)

    item.specialist_status = 'confirmed'
    item.confirmed_by = 1
    item.confirmed_at = datetime.now(timezone.utc)
    if data and data.notes:
        item.specialist_notes = data.notes

    db.commit()
    db.refresh(item)

    return ResponseWrapper(data=FormalReviewItemResponse.model_validate(item))


# ─── 5. POST /formal-review-items/{item_id}/correct ────────────────────────

@router.post("/formal-review-items/{item_id}/correct")
def correct_formal_review_item(
    item_id: int,
    data: ReviewItemCorrectRequest,
    db: Session = Depends(get_db),
):
    """
    Mark a review item as corrected.
    Sets specialist_status='corrected', corrected_evidence, specialist_notes.
    """
    item = _get_review_item_or_404(db, item_id)

    item.specialist_status = 'corrected'
    item.corrected_evidence = data.corrected_evidence
    item.specialist_notes = data.notes

    db.commit()
    db.refresh(item)

    return ResponseWrapper(data=FormalReviewItemResponse.model_validate(item))


# ─── 6. POST /formal-review-items/{item_id}/delete ────────────────────────

@router.post("/formal-review-items/{item_id}/delete")
def delete_formal_review_item(
    item_id: int,
    data: ReviewItemConfirmRequest = None,
    db: Session = Depends(get_db),
):
    """
    Mark a review item as deleted.
    Sets specialist_status='deleted', specialist_notes.
    """
    item = _get_review_item_or_404(db, item_id)

    item.specialist_status = 'deleted'
    if data and data.notes:
        item.specialist_notes = data.notes

    db.commit()
    db.refresh(item)

    return ResponseWrapper(data=FormalReviewItemResponse.model_validate(item))


# ─── 7. POST /projects/{project_id}/formal-review/manual-add ────────────────

@router.post("/projects/{project_id}/formal-review/manual-add")
def manual_add_review_item(
    project_id: int,
    data: ManualReviewItemRequest,
    db: Session = Depends(get_db),
):
    """
    Manually add a new formal review checklist item.
    """
    _get_project_or_404(db, project_id)

    item = FormalReviewItem(
        project_id=project_id,
        source_type='manual_added',
        check_category=data.check_category,
        check_title=data.check_title,
        check_description=data.check_description,
        reference_clause=data.reference_clause,
        system_status='pending',
        risk_level=data.risk_level,
        specialist_status='pending',
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return ResponseWrapper(data=FormalReviewItemResponse.model_validate(item))


# ─── 8. POST /projects/{project_id}/final-documents/generate ────────────────

@router.post("/projects/{project_id}/final-documents/generate")
def generate_final_document(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Generate final bid Word document after checking fatal items are resolved.

    1. Check fatal_pending via _check_can_generate
    2. Load project, tech_proposal, pricing_decision from DB
    3. Build tech_sections and pricing_data dicts
    4. Generate to /tmp/final_bid_{project_id}_{timestamp}.docx
    5. Save FinalBidDocument record
    6. Return FinalDocGenerateResponse
    """
    _get_project_or_404(db, project_id)

    # 1. Check fatal items
    can_generate, blocking_reason = _check_can_generate(db, project_id)
    if not can_generate:
        raise HTTPException(status_code=400, detail=blocking_reason)

    # 2. Load project
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # 3. Load tech_proposal (latest confirmed)
    tech_proposal = (
        db.query(TechProposalTask)
        .filter(
            TechProposalTask.project_id == project_id,
            TechProposalTask.status == 'confirmed',
        )
        .first()
    )

    # Build tech_sections from generated_content
    tech_sections = {"sections": []}
    if tech_proposal and tech_proposal.generated_content:
        content = tech_proposal.generated_content
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                content = {}
        if "sections" in content:
            tech_sections = content
        elif isinstance(content, dict):
            # Try to extract sections from dict
            tech_sections = {"sections": content.get("sections", [])}

    # 4. Load pricing_decision
    pricing_decision = (
        db.query(PricingDecision)
        .filter(
            PricingDecision.project_id == project_id,
            PricingDecision.status == 'decided',
        )
        .order_by(PricingDecision.id.desc())
        .first()
    )

    # Build pricing_data dict
    pricing_data = {}
    if pricing_decision:
        pricing_data = {
            "cost_base": float(pricing_decision.cost_base) if pricing_decision.cost_base else None,
            "system_suggested_low": float(pricing_decision.system_suggested_low) if pricing_decision.system_suggested_low else None,
            "system_suggested_high": float(pricing_decision.system_suggested_high) if pricing_decision.system_suggested_high else None,
            "boss_final_price": float(pricing_decision.boss_final_price) if pricing_decision.boss_final_price else None,
            "budget_limit": float(pricing_decision.budget_limit) if pricing_decision.budget_limit else None,
            "decision_reason": pricing_decision.boss_decision_reason,
        }

    # 5. Generate to temp path
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, f"final_bid_{project_id}_{timestamp}.docx")

    result = FinalBidWordGenerator.generate_final_document(
        project_id=project_id,
        tech_sections=tech_sections,
        pricing_data=pricing_data,
        output_path=output_path,
        db=db,
    )

    # 6. Save FinalBidDocument record
    doc_record = FinalBidDocument(
        project_id=project_id,
        document_type='final_bid',
        file_path=result["file_path"],
        file_size=result.get("file_size"),
        generated_by=1,
        generation_status=result.get("status", "completed"),
        packaging_guide=result.get("packaging_guide"),
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    return ResponseWrapper(data=FinalDocGenerateResponse(
        id=doc_record.id,
        project_id=project_id,
        file_path=result["file_path"],
        file_size=result.get("file_size"),
        generation_status=result.get("status", "completed"),
        packaging_guide=result.get("packaging_guide"),
    ))


# ─── 9. POST /projects/{project_id}/abandon ────────────────────────────────

@router.post("/projects/{project_id}/abandon")
def abandon_project(
    project_id: int,
    data: dict,
    db: Session = Depends(get_db),
):
    """
    Archive a project to abandoned_drafts during formal review.

    Body: {reason: str, user_id: int}
    """
    _get_project_or_404(db, project_id)

    reason = data.get("reason", "")
    user_id = data.get("user_id", 1)

    from app.core.week5_formal_review.formal_review_engine import (
        archive_project_to_abandoned_drafts,
    )
    archive_project_to_abandoned_drafts(
        db=db,
        project_id=project_id,
        termination_stage='formal_review',
        termination_reason=reason,
        user_id=user_id,
    )

    # Fetch the created record
    draft = (
        db.query(AbandonedDraft)
        .filter(AbandonedDraft.project_id == project_id)
        .order_by(AbandonedDraft.id.desc())
        .first()
    )

    return AbandonedDraftResponse.model_validate(draft)
