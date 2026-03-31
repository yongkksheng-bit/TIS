from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List

from app.models.base import Base, TimestampMixin
from app.models.enums import ParsingStatus, DocType, ImageType, OcrStatus


class TenderDocument(Base, TimestampMixin):
    """Tender document model representing parsed招标文件."""

    __tablename__ = "tender_documents"
    __table_args__ = (UniqueConstraint("project_id", name="uq_tender_documents_project_id"),)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    parsing_status: Mapped[ParsingStatus] = mapped_column(
        String(20), default=ParsingStatus.PENDING, nullable=False
    )
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    parsed_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_by_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Precise tender document identifiers (extracted via regex from PDF)
    plan_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)        # 采购计划编号
    agency_project_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 采购项目编号

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="tender_documents")


class BidDocument(Base, TimestampMixin):
    """Bid document model representing投标文件."""

    __tablename__ = "bid_documents"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    doc_type: Mapped[DocType] = mapped_column(String(50), nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="bid_documents")
    document_images: Mapped[List["DocumentImage"]] = relationship(
        "DocumentImage", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentImage(Base, TimestampMixin):
    """Document image model representing scanned images extracted from PDFs."""

    __tablename__ = "document_images"

    document_id: Mapped[int] = mapped_column(
        ForeignKey("bid_documents.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )

    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    image_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    image_type: Mapped[ImageType] = mapped_column(
        String(50), default=ImageType.OTHER, nullable=False
    )

    ocr_status: Mapped[OcrStatus] = mapped_column(
        String(20), default=OcrStatus.PENDING, nullable=False
    )

    # Relationships
    document: Mapped["BidDocument"] = relationship("BidDocument", back_populates="document_images")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="document_images")
    ocr_extractions: Mapped[List["OcrExtraction"]] = relationship(
        "OcrExtraction", back_populates="image", cascade="all, delete-orphan"
    )


# Import at bottom to avoid circular imports
from app.models.project import Project
from app.models.ocr import OcrExtraction
