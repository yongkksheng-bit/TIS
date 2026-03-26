"""Week 5 Pydantic schemas for formal review and final bid generation."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class FormalReviewItemResponse(BaseModel):
    id: int
    project_id: int
    source_type: str
    parent_item_id: Optional[int] = None
    check_category: str
    check_title: str
    check_description: Optional[str] = None
    reference_clause: Optional[str] = None
    system_status: str
    system_evidence: Optional[dict] = None
    specialist_status: str = 'pending'
    specialist_notes: Optional[str] = None
    corrected_evidence: Optional[str] = None
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    pdf_highlight_coords: Optional[dict] = None
    risk_level: str
    model_config = ConfigDict(from_attributes=True)


class FormalReviewStatusResponse(BaseModel):
    project_id: int
    total_items: int
    confirmed_items: int
    fatal_pending: int
    warning_pending: int
    can_generate: bool
    blocking_reason: Optional[str] = None


class ReviewItemConfirmRequest(BaseModel):
    notes: Optional[str] = Field(None, description="人工确认备注")


class ReviewItemCorrectRequest(BaseModel):
    corrected_status: str = Field(..., description="'passed' or 'warning'")
    corrected_evidence: str = Field(..., description="修正证据（页码或图片路径）")
    notes: str = Field(..., min_length=1, description="修正原因")


class ManualReviewItemRequest(BaseModel):
    check_category: str = Field(..., description="检查类别")
    check_title: str = Field(..., min_length=1, description="检查标题")
    check_description: str = Field(..., description="详细描述")
    risk_level: str = Field(..., description="fatal/warning/info")
    reference_clause: Optional[str] = Field(None, description="关联招标文件条款")
    pdf_page: Optional[int] = Field(None, description="关联PDF页码")


class FinalDocGenerateRequest(BaseModel):
    include_packaging_guide: bool = Field(True, description="是否生成封装指南")
    document_format: str = Field('word', description="文档格式（目前仅支持word）")


class FinalDocGenerateResponse(BaseModel):
    id: int
    project_id: int
    file_path: str
    file_size: Optional[int] = None
    generation_status: str
    packaging_guide: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)


class AbandonedDraftResponse(BaseModel):
    id: int
    project_id: int
    termination_stage: Optional[str]
    termination_reason: Optional[str]
    can_be_revived: bool
    archived_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)
