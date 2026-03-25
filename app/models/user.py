"""User model - minimal implementation for foreign key references."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Minimal User model for foreign key references.

    This is a placeholder model to satisfy foreign key constraints
    in other models like Project.created_by.
    """

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
