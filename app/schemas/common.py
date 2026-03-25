from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional

T = TypeVar("T")


class Page(BaseModel):
    """Pagination metadata."""

    page: int
    page_size: int
    total: int
    pages: int


class ResponseWrapper(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class ListResponse(BaseModel, Generic[T]):
    """Standard list response with pagination."""

    items: List[T]
    page: Page
