from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.schemas.evaluation import (
    EvaluationGenerateRequest, EvaluationReportResponse
)
from app.schemas.approval import (
    SpecialistApprovalRequest, SpecialistApprovalResponse,
    BossOverrideRequest, BossOverrideResponse
)
from app.schemas.common import ResponseWrapper
from app.core.week2_evaluation.evaluation_engine import BidEvaluationEngine
from app.core.week2_evaluation.approval_service import ApprovalWorkflowService
from app.models.evaluation import BidEvaluationReport
from app.models.project import Project

router = APIRouter(prefix="/api/v1", tags=["evaluations"])


@router.post("/projects/{project_id}/evaluations/generate")
def generate_evaluation_report(
    project_id: int,
    data: EvaluationGenerateRequest | None = None,
    db: Session = Depends(get_db)
):
    try:
        user_inputs = data.model_dump() if data else None
        engine = BidEvaluationEngine(db, project_id)
        result = engine.generate_report(user_inputs)
        # Wrap in ResponseWrapper
        return ResponseWrapper(data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/evaluations/latest")
def get_latest_evaluation(project_id: int, db: Session = Depends(get_db)):
    report = db.query(BidEvaluationReport).filter_by(
        project_id=project_id
    ).order_by(BidEvaluationReport.report_version.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No evaluation report found")
    # Serialize to dict matching the same format as generate_report
    result = {
        'report_id': report.id,
        'qualification': {
            'qualification_match_score': report.qualification_match_score,
            'is_qualification_pass': report.qualification_match_score >= 60,
            'missing_mandatory_certs': report.missing_mandatory_certs or [],
            'missing_optional_certs': report.missing_optional_certs or [],
            'matched_certs': report.matched_certs_detail or [],
        },
        'time': {
            'days_until_bid_open': report.days_until_bid_open,
            'time_urgency_level': report.time_urgency_level.value if hasattr(report.time_urgency_level, 'value') else report.time_urgency_level,
            'is_time_sufficient': report.is_time_sufficient,
        },
        'owner': {
            'owner_profile_id': report.owner_profile_id,
            'relationship_index': report.relationship_index,
            'is_new_owner': report.is_new_owner,
        },
        'cost': {
            'estimated_cost': float(report.estimated_cost) if report.estimated_cost else 0.0,
            'suggested_price_range_low': float(report.suggested_price_range_low) if report.suggested_price_range_low else 0.0,
            'suggested_price_range_high': float(report.suggested_price_range_high) if report.suggested_price_range_high else 0.0,
            'cost_estimate_confidence': report.cost_estimate_confidence.value if hasattr(report.cost_estimate_confidence, 'value') else report.cost_estimate_confidence,
        },
        'probability': {
            'overall_win_probability': float(report.overall_win_probability) if report.overall_win_probability else 0.0,
        },
        'recommendation': {
            'recommendation': report.recommendation.value if hasattr(report.recommendation, 'value') else report.recommendation,
            'recommendation_reason': report.recommendation_reason or '',
        },
        'risks': {
            'fatal_risks': report.fatal_risks or [],
            'warning_risks': report.warning_risks or [],
            'risk_level': report.risk_level.value if hasattr(report.risk_level, 'value') else report.risk_level,
        },
    }
    return ResponseWrapper(data=result)


@router.post("/evaluations/{report_id}/approve")
def specialist_approve(
    report_id: int,
    data: SpecialistApprovalRequest,
    db: Session = Depends(get_db)
):
    try:
        service = ApprovalWorkflowService(db)
        service.process_specialist_approval(
            report_id=report_id,
            action=data.action,
            generation_mode=data.generation_mode,
            user_id=data.user_id,
            override_reason=data.override_reason
        )
        # Get updated project status
        report = db.get(BidEvaluationReport, report_id)
        project = db.get(Project, report.project_id) if report else None
        project_status = project.status.value if project and hasattr(project.status, 'value') else str(project.status) if project else None
        return ResponseWrapper(data={"status": "success", "project_status": project_status})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/evaluations/{report_id}/override")
def boss_override(
    report_id: int,
    data: BossOverrideRequest,
    db: Session = Depends(get_db)
):
    try:
        service = ApprovalWorkflowService(db)
        service.process_boss_override(
            report_id=report_id,
            new_action=data.new_action,
            new_mode=data.new_mode,
            reason=data.reason,
            user_id=data.user_id
        )
        # Get updated project status
        report = db.get(BidEvaluationReport, report_id)
        project = db.get(Project, report.project_id) if report else None
        project_status = project.status.value if project and hasattr(project.status, 'value') else str(project.status) if project else None
        return ResponseWrapper(data={"status": "success", "new_status": project_status})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
