from pydantic import BaseModel
from typing import Any


class ChunkNode(BaseModel):
    """Schema for a single text chunk returned by the TextChunker."""
    text: str                          # chunk content
    chunk_index: int                    # sequential index (0-based)
    char_length: int                    # len(text)
    metadata: dict[str, Any]           # inherited metadata from source
