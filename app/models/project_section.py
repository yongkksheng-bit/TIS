"""ProjectSection model — persistent section storage for tech proposals.

Each project owns N named sections (e.g. "项目理解", "公司概况").
Content is independently upserted per section, replacing JSON blob storage.

UniqueConstraint(project_id, section_name) prevents duplicate section names
within the same project.
"""
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ProjectSection(Base, TimestampMixin):
    """Persistent storage for individual tech-proposal sections.

    id, created_at, updated_at are inherited from TimestampMixin.
    """

    __tablename__ = "project_sections"
    __table_args__ = (
        UniqueConstraint('project_id', 'section_name', name='uq_project_section_name'),
    )

    # id, created_at, updated_at — inherited from TimestampMixin (primary key + timestamps)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationship to parent project (defined here to satisfy back_populates)
    project: Mapped["Project"] = relationship("Project", back_populates="sections")
