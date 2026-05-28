from pydantic import BaseModel
from typing import Optional, Any, Literal


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


class ExtractionConfirmation(BaseModel):
    """Confirmation record for a single OCR extraction field."""
    extraction_id: int
    action: Literal["confirm", "correct"]
    corrected_value: Optional[str] = None
    corrected_cert_id: Optional[int] = None
    notes: Optional[str] = None


class ConfirmParsingRequest(BaseModel):
    confirmations: list[ExtractionConfirmation]
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


class TrashProject(BaseModel):
    """回收站项目响应"""
    id: int
    project_name: str
    project_type: str
    owner_unit: str
    region: str
    budget_amount: float
    status: str
    plan_code: Optional[str]
    agency_project_code: Optional[str]
    created_at: str


class RestoreResponse(BaseModel):
    """恢复项目响应"""
    message: str
    project_id: int
    project_name: str
    is_deleted: bool


class HardDeleteResponse(BaseModel):
    """物理删除响应"""
    project_id: int
    project_name: str
    minio_deleted: int
    vector_deleted: int
    db_deleted: bool


class ClearTrashResponse(BaseModel):
    """清空回收站响应"""
    cleared: list[HardDeleteResponse]
    errors: list[dict]
