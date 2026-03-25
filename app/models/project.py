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
    generation_mode: Mapped[Optional[GenerationMode]] = mapped_column(
        String(20), nullable=True
    )

    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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
