from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from typing import Optional, List

from app.models.base import Base, TimestampMixin
from app.models.enums import CertCategory


class StandardCertification(Base, TimestampMixin):
    """Standard certification model representing the certification standard library."""

    __tablename__ = "standard_certifications"

    cert_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    cert_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cert_short_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    aliases: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 匹配规则
    required_keywords: Mapped[dict] = mapped_column(JSONB, nullable=False)
    exclude_keywords: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 识别特征
    cert_number_pattern: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issuing_authority_keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # 业务属性
    category: Mapped[CertCategory] = mapped_column(String(50), nullable=True)
    validity_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_mandatory_for_food_delivery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mandatory_for_property: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    ocr_extractions: Mapped[List["OcrExtraction"]] = relationship(
        "OcrExtraction", foreign_keys="OcrExtraction.standard_cert_id"
    )


# Import at bottom to avoid circular imports
from app.models.ocr import OcrExtraction
