from sqlalchemy import String, Integer, DECIMAL, Date, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import OwnerType, RelationshipLevel

class OwnerProfile(Base, TimestampMixin):
    __tablename__ = "owner_profiles"

    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_type: Mapped[OwnerType] = mapped_column(String(50), nullable=True)
    region: Mapped[str] = mapped_column(String(100), nullable=True)
    cooperation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_cooperation_date: Mapped[Date] = mapped_column(Date, nullable=True)
    relationship_level: Mapped[RelationshipLevel] = mapped_column(String(20), default=RelationshipLevel.NONE)
    avg_winning_discount: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=True)
    preferred_styles: Mapped[dict] = mapped_column(JSON, nullable=True)
    common_requirements: Mapped[list] = mapped_column(JSON, nullable=True)
    blacklist_flags: Mapped[list] = mapped_column(JSON, nullable=True)

    __table_args__ = (UniqueConstraint('owner_name', 'region'),)