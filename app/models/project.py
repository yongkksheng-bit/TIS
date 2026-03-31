from sqlalchemy import String, Boolean, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from typing import Optional, List

from app.models.base import Base, TimestampMixin
from app.models.enums import ProjectStatus, GenerationMode, OwnerType


class Project(Base, TimestampMixin):
    """Project model representing a tender/bid project."""

    __tablename__ = "projects"

    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    owner_unit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_type: Mapped[OwnerType] = mapped_column(
        String(50), default=OwnerType.ENTERPRISE, nullable=True
    )
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    budget_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    bid_open_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    status: Mapped[ProjectStatus] = mapped_column(
        String(50), default=ProjectStatus.UPLOADED, nullable=False
    )

    relationship_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    relation_identifier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    differentiation_guidance: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    generation_mode: Mapped[Optional[GenerationMode]] = mapped_column(
        String(20), nullable=True
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    is_retender: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    # Precise duplicate-detection codes (from real tender documents)
    plan_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)        # 采购计划编号
    agency_project_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 采购项目编号（可为空）

    # Soft-delete flag — SAFE DELETE pattern (商业 SaaS 标准实践)
    # - is_deleted = False: 正常项目，用户可见
    # - is_deleted = True:  已移入回收站，不出现在列表中
    # - 物理删除（hard delete）：未来扩展时，务必在 purge_hard_delete() 中实现，
    #   并在删除前做数据备份、审计日志记录、关联附件清理等安全检查。
    #   参见 approval_service.py 中的 _hard_delete_project() 预留钩子。
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True  # w012: composite index added
    )

    # Relationships
    tender_documents: Mapped[List["TenderDocument"]] = relationship(
        "TenderDocument", back_populates="project", cascade="all, delete-orphan"
    )
    bid_documents: Mapped[List["BidDocument"]] = relationship(
        "BidDocument", back_populates="project", cascade="all, delete-orphan"
    )
    document_images: Mapped[List["DocumentImage"]] = relationship(
        "DocumentImage", back_populates="project", cascade="all, delete-orphan"
    )
    ocr_extractions: Mapped[List["OcrExtraction"]] = relationship(
        "OcrExtraction", back_populates="project", cascade="all, delete-orphan"
    )


# Import at bottom to avoid circular imports
from app.models.document import TenderDocument, BidDocument, DocumentImage
from app.models.ocr import OcrExtraction
