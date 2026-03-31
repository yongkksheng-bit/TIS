from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models.project import Project
from app.schemas.document import ProjectCreate, UploadResponse, ConfirmParsingRequest
from app.core.week1_document.parser import DocumentOCRPipeline
from app.core.week1_document.confirmation_service import ConfirmationService

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Role-based project status filters
FINANCE_STATUSES = {"awaiting_pricing", "awaiting_review", "completed"}


def _project_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "project_name": p.project_name,
        "project_type": p.project_type or "",
        "owner_unit": p.owner_unit or "",
        "region": p.region or "",
        "budget_amount": float(p.budget_amount) if p.budget_amount else 0.0,
        "status": p.status.value if hasattr(p.status, "value") else str(p.status),
        "relationship_flag": p.relationship_flag,
        "generation_mode": p.generation_mode,
        "bid_open_date": str(p.bid_open_date) if p.bid_open_date else "",
        "is_retender": p.is_retender,
        "parent_project_id": p.parent_project_id,
        "plan_code": p.plan_code,
        "agency_project_code": p.agency_project_code,
    }


@router.get("", response_model=list)
def list_projects(
    role: str = Query("boss", description="Role for filtering: boss|specialist|finance"),
    db: Session = Depends(get_db),
):
    """
    List projects with role-based filtering.

    SOFT-DELETE: Only returns projects where is_deleted = False.
    Hard-delete (物理删除) is reserved as a future extension — see
    _hard_delete_project() in approval_service.py when implementing purge.
    """
    q = db.query(Project).filter(Project.is_deleted == False).order_by(Project.id.desc())

    if role == "specialist":
        # Specialist sees own projects; fall back to all if no user context
        current_user = get_current_user()
        if current_user and current_user.get("id"):
            q = q.filter(Project.created_by == current_user["id"])
    elif role == "finance":
        q = q.filter(Project.status.in_(FINANCE_STATUSES))
    # boss: no filter

    projects = q.all()
    return [_project_dict(p) for p in projects]


@router.post("", response_model=dict)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """
    Create a project with dual-key duplicate detection.

    Priority: plan_code > agency_project_code > project_name
    Non-active statuses excluded from duplicate check: discarded, terminated_by_boss

    Returns HTTP 409 Conflict with rich payload (existing_project_name, duplicate_code)
    unless force_retender=True (废标重招 flow).
    """
    # Non-dismissed statuses that still count as duplicates
    ACTIVE_STATUSES = {
        "uploaded", "parsing", "parsed", "evaluating", "evaluation_ready",
        "pending_boss_approval", "approved_by_specialist", "rejected_by_specialist",
        "generating_documents", "awaiting_pricing", "awaiting_review", "completed",
    }

    def _is_active(p: Project) -> bool:
        s = p.status.value if hasattr(p.status, "value") else str(p.status)
        return s in ACTIVE_STATUSES

    duplicate_code = None
    existing_project_name = None
    existing = None

    if not data.force_retender:
        # Step 1: Check plan_code first (most precise identifier)
        # IMPORTANT: is_deleted=False ensures soft-deleted (回收站) projects are invisible to duplicate check
        if data.plan_code:
            existing = (
                db.query(Project)
                .filter(Project.plan_code == data.plan_code, Project.plan_code.isnot(None))
                .filter(Project.status.in_(ACTIVE_STATUSES))
                .filter(Project.is_deleted == False)  # w012: skip soft-deleted projects
                .first()
            )
            if existing:
                duplicate_code = f"采购计划编号：{data.plan_code}"
                existing_project_name = existing.project_name

        # Step 2: Check agency_project_code
        if not existing and data.agency_project_code:
            existing = (
                db.query(Project)
                .filter(Project.agency_project_code == data.agency_project_code, Project.agency_project_code.isnot(None))
                .filter(Project.status.in_(ACTIVE_STATUSES))
                .filter(Project.is_deleted == False)  # w012: skip soft-deleted projects
                .first()
            )
            if existing:
                duplicate_code = f"采购项目编号：{data.agency_project_code}"
                existing_project_name = existing.project_name

        # Step 3: Fallback to project_name
        if not existing and data.project_name:
            existing = (
                db.query(Project)
                .filter(Project.project_name == data.project_name)
                .filter(Project.status.in_(ACTIVE_STATUSES))
                .filter(Project.is_deleted == False)  # w012: skip soft-deleted projects
                .first()
            )
            if existing:
                duplicate_code = f"项目名称：{data.project_name}"
                existing_project_name = existing.project_name

        if existing:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "DUPLICATE_TENDER",
                    "message": f"系统已存在相同项目「{existing_project_name}」",
                    "existing_project_name": existing_project_name,
                    "duplicate_code": duplicate_code,
                    "existing_project_id": existing.id,
                    "existing_status": existing.status.value
                    if hasattr(existing.status, "value")
                    else str(existing.status),
                },
            )

    # Build project
    project = Project(
        project_name=data.project_name,
        owner_unit=data.owner_unit,
        status="uploaded",
        is_retender=data.force_retender,
        parent_project_id=data.parent_id if data.force_retender else None,
        plan_code=data.plan_code if data.plan_code else None,
        agency_project_code=data.agency_project_code if data.agency_project_code else None,
    )

    # Attach current user if available
    current_user = get_current_user()
    if current_user and current_user.get("id"):
        project.created_by = current_user["id"]

    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "status": project.status, "is_retender": project.is_retender}

@router.post("/{project_id}/upload")
async def upload_document(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if file.content_type not in ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        raise HTTPException(400, "Only PDF or Word files supported")

    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    import tempfile
    from pathlib import Path
    tmp_dir = Path(tempfile.gettempdir()) / "tis_uploads"
    tmp_dir.mkdir(exist_ok=True)
    tmp_file = tmp_dir / f"{project_id}_{file.filename}"
    tmp_file.write_bytes(await file.read())

    project.status = 'parsing'
    db.commit()

    pipeline = DocumentOCRPipeline(db)
    result = pipeline.process_pdf(str(tmp_file), project_id)

    return {"file_id": project_id, "upload_status": "success", "processed_images": result['processed_images']}

@router.get("/{project_id}/confirmation-data")
def get_confirmation_data(project_id: int, db: Session = Depends(get_db)):
    service = ConfirmationService(db)
    try:
        return service.get_confirmation_data(project_id)
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/{project_id}", response_model=dict)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,  # Exclude soft-deleted projects
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")
    return {
        "id": project.id,
        "project_name": project.project_name,
        "project_type": project.project_type,
        "owner_unit": project.owner_unit,
        "region": project.region,
        "budget_amount": float(project.budget_amount) if project.budget_amount else 0,
        "status": project.status.value if hasattr(project.status, "value") else project.status,
        "relationship_flag": project.relationship_flag,
        "generation_mode": project.generation_mode,
        "bid_open_date": str(project.bid_open_date) if project.bid_open_date else "",
        "is_retender": project.is_retender,
        "parent_project_id": project.parent_project_id,
    }


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """
    Soft-delete a project (SAFE DELETE pattern).

    Sets is_deleted = True instead of physically removing the row.
    The project disappears from all list queries but can be recovered
    by an administrator with a hard-delete purge operation.

    HARD-DELETE extension point (未来扩展):
        To permanently remove a project and all its data:
        1. Archive the project record to a separate audit table
        2. Delete related TenderDocument, BidDocument, DocumentImage rows first
        3. Then DELETE FROM projects WHERE id = :id
        4. Purge MinIO/S3 file storage for the project
        See approval_service.py _hard_delete_project() for the implementation stub.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == False,
    ).first()
    if not project:
        raise HTTPException(404, "Project not found")

    project.is_deleted = True
    db.commit()
    return {
        "message": "项目已移入回收站",
        "project_id": project_id,
        "project_name": project.project_name,
        "is_deleted": True,  # 明确告知前端字段状态，供直接使用
    }

@router.post("/{project_id}/confirm-parsing")
def confirm_parsing(project_id: int, data: ConfirmParsingRequest, db: Session = Depends(get_db)):
    project = db.query(Project).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # Update project fields with any corrections from confirmation page
    # Note: relationship_flag and differentiation_guidance are set in Week 2, not here
    if data.project_name is not None:
        project.project_name = data.project_name
    if data.owner_unit is not None:
        project.owner_unit = data.owner_unit
    if data.budget_amount is not None:
        project.budget_amount = data.budget_amount
    if data.region is not None:
        project.region = data.region
    if data.project_type is not None:
        project.project_type = data.project_type
    if data.bid_open_date is not None and data.bid_open_date != '':
        try:
            project.bid_open_date = datetime.strptime(data.bid_open_date, '%Y-%m-%d')
        except ValueError:
            pass  # ignore invalid date format, leave existing value
    if data.plan_code is not None:
        project.plan_code = data.plan_code
    if data.agency_project_code is not None:
        project.agency_project_code = data.agency_project_code

    # Handle extraction confirmations
    service = ConfirmationService(db)
    current_user_id = 1  # placeholder

    for conf in data.confirmations:
        try:
            if conf.action == 'correct':
                service.apply_correction(conf.extraction_id, conf.corrected_value, conf.corrected_cert_id, current_user_id, conf.notes)
            elif conf.action == 'confirm':
                service.confirm_extraction(conf.extraction_id, current_user_id)
        except ValueError as e:
            raise HTTPException(400, str(e))

    result = service.confirm_all(project_id, current_user_id)
    if not result['success']:
        raise HTTPException(400, result['error'])

    # Refresh to get updated status
    db.refresh(project)
    new_status = project.status.value if hasattr(project.status, 'value') else project.status
    return {"status": "confirmed", "project_status": new_status}


@router.put("/{project_id}/relationship")
def update_relationship(
    project_id: int,
    relationship_flag: bool,
    differentiation_guidance: Optional[str],
    db: Session = Depends(get_db),
):
    """
    Update the relationship flag for a project (Week 2 specialist/boss decision).

    If the project is already past EVALUATION_READY and the flag changed, triggers
    a forced rollback to clear tech proposal and pricing data.

    Relationship flag is DECOUPLED from generation mode — they are independent.
    """
    from app.core.week2_evaluation.approval_service import ApprovalWorkflowService

    service = ApprovalWorkflowService(db)
    current_user = get_current_user()
    user_id = current_user.get("id") if current_user else 1

    try:
        result = service.process_relationship_change(
            project_id=project_id,
            relationship_flag=relationship_flag,
            differentiation_guidance=differentiation_guidance,
            user_id=user_id,
        )
        return {
            "relationship_flag": relationship_flag,
            "differentiation_guidance": differentiation_guidance,
            "rolled_back": result["rolled_back"],
            "new_status": result["new_status"],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
