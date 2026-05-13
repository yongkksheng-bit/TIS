import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models.project import Project
from app.models.enums import ProjectStatus
from app.schemas.document import ProjectCreate, UploadResponse, ConfirmParsingRequest
from app.core.week1_document.parser import DocumentOCRPipeline
from app.core.week1_document.confirmation_service import ConfirmationService

router = APIRouter(prefix="/api/projects", tags=["projects"])

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Hard Delete (物理删除) — 三方联动清理
# ---------------------------------------------------------------------------

@router.get("/trash")
def list_trash(db: Session = Depends(get_db)):
    """
    列出所有已进入回收站的项目（is_deleted = True）。
    供 TrashView 回收站管理界面使用。
    """
    projects = (
        db.query(Project)
        .filter(Project.is_deleted == True)
        .order_by(Project.id.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "project_name": p.project_name,
            "project_type": p.project_type or "",
            "owner_unit": p.owner_unit or "",
            "region": p.region or "",
            "budget_amount": float(p.budget_amount) if p.budget_amount else 0.0,
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "plan_code": p.plan_code,
            "agency_project_code": p.agency_project_code,
            "created_at": str(p.created_at) if p.created_at else "",
        }
        for p in projects
    ]


@router.post("/clear-trash")
def clear_trash(db: Session = Depends(get_db)):
    """
    批量永久删除所有已进入回收站的项目（清空回收站）。

    遍历所有 is_deleted=True 的项目，分别执行三方联动清理。
    MinIO/pgvector 失败不影响 DB 提交。

    Returns:
        {cleared: [{project_id, project_name, minio_deleted, vector_deleted}], errors: []}
    """
    from app.core.hard_delete import hard_delete_project as _hard_delete

    trash_projects = (
        db.query(Project)
        .filter(Project.is_deleted == True)
        .all()
    )

    if not trash_projects:
        return {"cleared": [], "errors": []}

    cleared = []
    errors = []

    for project in trash_projects:
        # 提前捕获，避免事务回滚后访问已分离的 ORM 对象
        pid = project.id
        pname = project.project_name
        try:
            result = _hard_delete(db, pid)
            cleared.append(result)
        except Exception as e:
            logger.error(f"clear_trash: failed to hard-delete project {pid} ({pname}): {e}")
            errors.append({
                "project_id": pid,
                "project_name": pname,
                "error": str(e),
            })

    return {"cleared": cleared, "errors": errors}


@router.post("/{project_id}/restore")
def restore_project(project_id: int, db: Session = Depends(get_db)):
    """
    从回收站恢复项目（is_deleted = False）。
    恢复后项目重新出现在常规列表中。
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.is_deleted == True,
    ).first()
    if not project:
        raise HTTPException(404, "回收站中找不到该项目")

    project.is_deleted = False
    db.commit()
    return {
        "message": "项目已从回收站恢复",
        "project_id": project_id,
        "project_name": project.project_name,
        "is_deleted": False,
    }


@router.post("/{project_id}/clone")
def clone_project(
    project_id: int,
    data: dict,
    db: Session = Depends(get_db),
):
    """
    Clone a project (retender / annual renewal) with full section asset inheritance.

    Body:
        clone_type: "rebid" | "annual_renewal"
        new_name:   Optional[str] — override generated name (e.g. "xxx - 2025")
        plan_code:  Optional[str] — for annual_renewal, the newly parsed plan_code

    For "rebid":
        - new project gets parent_project_id = source_id
        - plan_code inherits from source project
        - name = source.name + " - 重投" (deduped)

    For "annual_renewal":
        - new project parent_project_id = NULL
        - plan_code comes from request body (newly parsed from new PDF)
        - name = source.name + " - {year}" or source.name + " - 新一期"

    Asset inheritance (both types):
        - Copies all ProjectSection records from source → new project
    """
    from app.models.project_section import ProjectSection

    clone_type = data.get("clone_type")
    if clone_type not in ("rebid", "annual_renewal"):
        raise HTTPException(status_code=400, detail="clone_type must be 'rebid' or 'annual_renewal'")

    source = db.get(Project, project_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    # ── Naming ──────────────────────────────────────────────────────────────────
    base_name = source.project_name
    year = None

    if clone_type == "rebid":
        suffix = " - 重投"
        dedup_name = base_name + suffix
        # Deduplicate: if "xxx - 重投" already exists, try "xxx - 重投 (2)"
        counter = 1
        while (
            db.query(Project)
            .filter(Project.project_name == dedup_name, Project.is_deleted == False)
            .first()
        ):
            counter += 1
            dedup_name = f"{base_name} - 重投 ({counter})"
        new_name = dedup_name
        plan_code_to_use = source.plan_code  # inherits same plan_code for retender

    else:  # annual_renewal
        plan_code_to_use = data.get("plan_code") or source.plan_code
        year = data.get("year")
        if year:
            suffix = f" - {year}"
        else:
            suffix = " - 新一期"
        dedup_name = base_name + suffix
        counter = 1
        while (
            db.query(Project)
            .filter(Project.project_name == dedup_name, Project.is_deleted == False)
            .first()
        ):
            counter += 1
            dedup_name = f"{base_name}{suffix} ({counter})"
        new_name = dedup_name

    # ── Create new project ──────────────────────────────────────────────────────
    new_project = Project(
        project_name=new_name,
        owner_unit=source.owner_unit,
        project_type=source.project_type,
        region=source.region,
        budget_amount=source.budget_amount,
        bid_open_date=source.bid_open_date,
        status=ProjectStatus.UPLOADED.value,
        plan_code=plan_code_to_use,
        agency_project_code=source.agency_project_code,
        is_retender=(clone_type == "rebid"),
        parent_project_id=project_id if clone_type == "rebid" else None,
        relationship_flag=False,
        generation_mode=None,
        created_by=source.created_by,
    )
    db.add(new_project)
    db.flush()  # get new_project.id

    # ── Copy ProjectSection records ──────────────────────────────────────────────
    source_sections = (
        db.query(ProjectSection)
        .filter(ProjectSection.project_id == project_id)
        .all()
    )
    for sec in source_sections:
        db.add(ProjectSection(
            project_id=new_project.id,
            section_name=sec.section_name,
            content=sec.content,
        ))

    db.commit()
    db.refresh(new_project)

    return {
        "new_project_id": new_project.id,
        "new_project_name": new_project.project_name,
        "clone_type": clone_type,
        "parent_project_id": project_id if clone_type == "rebid" else None,
        "sections_copied": len(source_sections),
    }


@router.delete("/{project_id}/hard-delete")
def hard_delete_project(project_id: int, db: Session = Depends(get_db)):
    """
    物理删除项目（永久销毁）。

    三方联动清理顺序：
    1. PostgreSQL：验证项目存在且已软删除
    2. MinIO：删除该项目所有归档文件对象（非阻塞）
    3. pgvector：删除 knowledge_chunks 中 source_project_id = project_id 的向量片段（非阻塞）
    4. PostgreSQL：CASCADE 自动清理关联行后删除主记录

    Returns:
        {project_id, project_name, minio_deleted, vector_deleted, db_deleted}
    """
    from app.core.hard_delete import hard_delete_project as _hard_delete

    result = _hard_delete(db, project_id)
    return result


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
    try:
        result = pipeline.process_pdf(str(tmp_file), project_id)
    except Exception as e:
        db.rollback()
        project.status = 'parse_failed'
        db.commit()
        raise HTTPException(500, f"文件解析失败：{e}")

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


@router.post("/{project_id}/advance-to-pricing")
def advance_to_pricing(
    project_id: int,
    db: Session = Depends(get_db),
):
    """
    Advance project from 'generating_documents' to 'awaiting_pricing'.

    Called by TechProposalView.confirmAllSections() after all tech proposal
    sections have been confirmed by the specialist.

    This is the bridge between Week 3 (tech proposal generation) and
    Week 4 (pricing decision).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, f"Project {project_id} not found")

    if project.status != ProjectStatus.GENERATING_DOCUMENTS.value:
        raise HTTPException(
            400,
            f"项目状态为 '{project.status}'，只能在 'generating_documents' 状态下推进到定价"
        )

    project.status = ProjectStatus.AWAITING_PRICING.value
    db.commit()

    return {
        "message": "项目已推进到定价阶段",
        "project_id": project_id,
        "new_status": project.status,
    }
