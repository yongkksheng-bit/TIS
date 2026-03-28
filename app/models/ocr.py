from sqlalchemy import String, Text, Boolean, ForeignKey, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List

from app.models.base import Base, TimestampMixin
from app.models.enums import OcrFieldName


class OcrExtraction(Base, TimestampMixin):
    """OCR extraction result model."""

    __tablename__ = "ocr_extractions"

    image_id: Mapped[int] = mapped_column(
        ForeignKey("document_images.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # OCR识别字段
    field_name: Mapped[OcrFieldName] = mapped_column(String(50), nullable=False)
    field_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)

    # 标准化后数据
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    standard_cert_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("standard_certifications.id", ondelete="SET NULL"), nullable=True
    )

    # 人工校验
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # OCR原始完整文本及坐标
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bbox_coords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    image: Mapped["DocumentImage"] = relationship("DocumentImage", back_populates="ocr_extractions")
    project: Mapped["Project"] = relationship("Project", back_populates="ocr_extractions")
    standard_certification: Mapped[Optional["StandardCertification"]] = relationship(
        "StandardCertification", back_populates="ocr_extractions"
    )


# Import at bottom to avoid circular imports
from app.models.document import DocumentImage
from app.models.project import Project
from app.models.standard import StandardCertification
