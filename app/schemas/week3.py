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
    # ── w015: historical asset RAG metadata (written to knowledge_chunks) ─────
    source_type: Optional[str] = Field(None, description="Source type: 'historical_tender', 'internal_postmortem', etc.")
    source_id: Optional[int] = Field(None, description="Foreign ID in the source system")
    source_label: Optional[str] = Field(None, description="Human-readable label for this chunk")
    win_signal: Optional[str] = Field(None, description="positive=成功经验 | negative=失败教训 | neutral=一般参考")
    scoring_dimension_tags: Optional[list[str]] = Field(None, description="评分维度标签，如['食材溯源','冷链管理']")
    region_tags: Optional[list[str]] = Field(None, description="地区标签，如['广东省','惠州市']")
    project_type_tags: Optional[list[str]] = Field(None, description="项目类型标签，如['服务类','食堂配送']")
    is_price_sensitive: bool = Field(default=False, description="Whether this chunk is price-sensitive")


class GenerateSectionRequest(BaseModel):
    """Request to generate a single section of a tech proposal."""
    section_name: str = Field(..., description="Section name, e.g. '第一章：冷链配送方案'")
    generation_mode: str = Field(..., pattern="^(auto|guided)$", description="'auto' or 'guided'")
    insider_notes: Optional[str] = Field(None, description="Required for guided mode; expert insider knowledge")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    # ── w015/w018: dual-track RAG filters (historical asset retrieval) ─────────
    scoring_dimension_tags: Optional[list[str]] = Field(
        None, description="Filter historical chunks by scoring dimension tags"
    )
    region_tags: Optional[list[str]] = Field(
        None, description="Filter historical chunks by region tags"
    )
    use_dual_track_rag: bool = Field(
        default=False,
        description="Whether to inject positive/negative historical samples into prompt",
    )


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
    """Response from section generation.

    token_usage follows DeepSeek API usage structure:
    {
        "prompt_tokens": int,
        "completion_tokens": int,
        "total_tokens": int,
        "prompt_tokens_details": {"cached_tokens": int, ...},  <-- dict, not int
        "completion_tokens_details": {"reasoning_tokens": int, ...}  <-- dict
    }
    """
    project_id: int
    section_name: str
    content: str
    mode: str
    token_usage: dict[str, Any]   # relaxed from dict[str, int] to accommodate DeepSeek nested details
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


class SectionUpsertRequest(BaseModel):
    """Upsert a single section (called after LLM generation or user re-generate)."""
    section_name: str
    content: str
    mode: str = "auto"


class SectionUpsertResponse(BaseModel):
    """Response after upserting a section."""
    project_id: int
    section_name: str
    content: str
    upserted: bool  # True=insert, False=update
    saved_at: str
