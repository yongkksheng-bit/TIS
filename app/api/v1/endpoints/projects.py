from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db, get_current_user
from app.models.project import Project
from app.schemas.document import ProjectCreate, UploadResponse, ConfirmParsingRequest
from app.core.week1_document.parser import DocumentOCRPipeline
from app.core.week1_document.confirmation_service import ConfirmationService

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.post("", response_model=dict)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(project_name=data.project_name, owner_unit=data.owner_unit, status='uploaded')
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "status": project.status}

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

@router.post("/{project_id}/confirm-parsing")
def confirm_parsing(project_id: int, data: ConfirmParsingRequest, db: Session = Depends(get_db)):
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
    return {"status": "confirmed"}
