from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.models.document import DocumentImage, OcrExtraction

router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/document-images/{image_id}/view")
def get_image_view(image_id: int, db: Session = Depends(get_db)):
    image = db.query(DocumentImage).get(image_id)
    if not image:
        raise HTTPException(404, "Image not found")
    return FileResponse(image.image_path)

@router.get("/ocr-extractions/{extraction_id}")
def get_extraction_detail(extraction_id: int, db: Session = Depends(get_db)):
    ext = db.query(OcrExtraction).get(extraction_id)
    if not ext:
        raise HTTPException(404, "Extraction not found")
    return {
        "id": ext.id,
        "field_name": ext.field_name,
        "field_value": ext.field_value,
        "normalized_value": ext.normalized_value,
        "confidence": float(ext.confidence_score),
        "is_validated": ext.is_validated,
        "standard_cert_id": ext.standard_cert_id,
    }
