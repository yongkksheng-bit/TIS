"""Week 3 Pydantic schemas for RAG API endpoints."""
from pydantic import BaseModel, Field
from typing import Optional, Any


# ─── Request Schemas ───────────────────────────────────────────────────────────

class EmbedDocumentRequest(BaseModel):
    """Request to chunk and embed a document."""
    content: str = Field(..., description="Full text content of the document to chunk")
    chunk_type: str = Field(default="technical", description="Type: 'qualification', 'technical', 'commercial'")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata to attach to chunks")
    chunk_size: int = Field(default=500, ge=100, le=2000, description="Max chars per chunk")


class GenerateSectionRequest(BaseModel):
    """Request to generate a single section of a tech proposal."""
    section_name: str = Field(..., description="Section name, e.g. '第一章：冷链配送方案'")
    generation_mode: str = Field(..., pattern="^(auto|guided)$", description="'auto' or 'guided'")
    insider_notes: Optional[str] = Field(None, description="Required for guided mode; expert insider knowledge")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")


# ─── Response Schemas ──────────────────────────────────────────────────────────

class ChunkInfo(BaseModel):
    """Info about a stored chunk."""
    chunk_id: int
    chunk_index: int
    char_length: int
    chunk_type: str


class EmbedDocumentResponse(BaseModel):
    """Response after chunking and embedding documents."""
    project_id: int
    chunks_stored: int
    chunks: list[ChunkInfo]


class GeneratedSectionResponse(BaseModel):
    """Response from section generation."""
    project_id: int
    section_name: str
    content: str
    mode: str
    token_usage: dict[str, int]
    source_chunk_count: int
    generation_timestamp: str


class SectionData(BaseModel):
    """Single section's generated data."""
    section_name: str
    content: str
    mode: str
    generation_timestamp: str


class GetSectionsResponse(BaseModel):
    """Response listing all generated sections for a project."""
    project_id: int
    sections: list[SectionData]
