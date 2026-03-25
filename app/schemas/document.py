from pydantic import BaseModel
from typing import Optional, Any


class ProjectCreate(BaseModel):
    project_name: Optional[str] = None
    owner_unit: Optional[str] = None


class UploadResponse(BaseModel):
    file_id: int
    upload_status: str
    processed_images: int
    extracted_preview: Optional[dict] = None


class ConfirmParsingRequest(BaseModel):
    confirmations: list[dict]  # {extraction_id, action, corrected_value?, corrected_cert_id?, notes?}


class ExtractionResponse(BaseModel):
    id: int
    field_name: str
    field_value: str
    normalized_value: Optional[str]
    confidence: float
    is_validated: bool
    standard_cert_suggestion: Optional[int]
    standard_cert_id: Optional[int]
