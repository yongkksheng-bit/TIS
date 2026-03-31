from pydantic import BaseModel
from typing import Optional, Any


class ProjectCreate(BaseModel):
    project_name: Optional[str] = None
    owner_unit: Optional[str] = None
    force_retender: bool = False  # Bypass duplicate check and force create as re-tender
    parent_id: Optional[int] = None  # Required when force_retender=True
    plan_code: Optional[str] = None          # 采购计划编号（精确防重第一键）
    agency_project_code: Optional[str] = None  # 采购项目编号（精确防重第二键）


class UploadResponse(BaseModel):
    file_id: int
    upload_status: str
    processed_images: int
    extracted_preview: Optional[dict] = None


class ConfirmParsingRequest(BaseModel):
    confirmations: list[dict]  # {extraction_id, action, corrected_value?, corrected_cert_id?, notes?}
    project_name: Optional[str] = None
    owner_unit: Optional[str] = None
    budget_amount: Optional[float] = None
    region: Optional[str] = None
    project_type: Optional[str] = None
    bid_open_date: Optional[str] = None
    plan_code: Optional[str] = None          # 采购计划编号（可手动修正）
    agency_project_code: Optional[str] = None  # 采购项目编号（可为空，可手动修正）


class ExtractionResponse(BaseModel):
    id: int
    field_name: str
    field_value: str
    normalized_value: Optional[str]
    confidence: float
    is_validated: bool
    standard_cert_suggestion: Optional[int]
    standard_cert_id: Optional[int]
