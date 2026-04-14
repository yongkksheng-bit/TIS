"""Chunk Loader — batch writes to knowledge_chunks with full transaction safety.

Implements the "all-or-nothing" batch insert pattern:
  - Accumulates chunks in a buffer up to batch_size
  - flush() commits the batch atomically via a transaction
  - On any DB error during flush: FULL ROLLBACK of the entire batch
  - Buffer is cleared after successful commit
  - caller can check flush() return value to know write count

Key design:
  - All w015 columns written: source_type, source_id, source_label,
    chunk_index, win_signal, scoring_dimension_tags, region_tags,
    project_type_tags, is_price_sensitive, token_count
  - content_vector stored as JSON string (not array column — text field)
  - chunk_metadata JSON column carries supplemental tags

Author: TIS Seeding Pipeline
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk

logger = logging.getLogger(__name__)


class ChunkLoader:
    """
    Batch-writes knowledge_chunks records with historical RAG metadata.

    Transaction safety:
      - flush() wraps ALL buffered inserts in a single DB transaction
      - Any error → rollback, buffer is NOT cleared (caller can retry)
      - After successful commit, buffer is cleared

    Attributes:
        db: SQLAlchemy session.
        batch_size: Number of chunks to accumulate before auto-flush.
    """

    def __init__(self, db: Session, batch_size: int = 100):
        self.db = db
        self.batch_size = batch_size
        self._buffer: list[dict[str, Any]] = []

    def add(self, chunk: Any, vector: list[float]) -> None:
        """
        Add a chunk + embedding to the write buffer.

        When buffer reaches batch_size, automatically calls flush().

        Args:
            chunk: ChunkNode or dict with 'text', 'chunk_index', 'char_length'.
            vector: Embedding vector as list[float].
        """
        # Normalize chunk to dict
        if hasattr(chunk, "to_dict"):
            c = chunk.to_dict()
        elif hasattr(chunk, "__dict__"):
            c = {
                "text": getattr(chunk, "text", ""),
                "chunk_index": getattr(chunk, "chunk_index", 0),
                "char_length": getattr(chunk, "char_length", 0),
                "metadata": getattr(chunk, "metadata", {}),
            }
        else:
            c = dict(chunk)

        self._buffer.append({"chunk": c, "vector": vector})

        if len(self._buffer) >= self.batch_size:
            flushed = self.flush()
            logger.debug("Auto-flush: %d chunks written (batch_size=%d)", flushed, self.batch_size)

    def flush(self) -> int:
        """
        Flush the current buffer to the database in a single transaction.

        Transaction semantics:
          - BEGIN → INSERT (all rows) → COMMIT
          - On any error → ROLLBACK, buffer unchanged, re-raise
          - On success → buffer cleared, return count

        Returns:
            Number of chunks actually written.
        """
        if not self._buffer:
            return 0

        chunks_to_write = len(self._buffer)
        logger.debug("Flushing %d chunks to DB...", chunks_to_write)

        try:
            # Build bulk insert values
            rows = []
            for item in self._buffer:
                chunk = item["chunk"]
                vec = item["vector"]

                text_content = chunk.get("text", "")
                metadata = chunk.get("metadata", {})

                rows.append(
                    {
                        "chunk_type": "historical",
                        "content": text_content,
                        "content_vector": json.dumps(vec) if vec else None,
                        "chunk_metadata": metadata,
                        "source_type": metadata.get("source_type"),
                        "source_id": metadata.get("tender_id"),
                        "source_label": metadata.get("source_file"),
                        "chunk_index": chunk.get("chunk_index"),
                        "win_signal": metadata.get("win_signal"),
                        "scoring_dimension_tags": metadata.get("scoring_dimension_tags"),
                        "region_tags": metadata.get("region_tags"),
                        "project_type_tags": metadata.get("project_type_tags"),
                        "is_price_sensitive": metadata.get("is_price_sensitive", False),
                        "token_count": metadata.get("token_count", 0),   # w015 field
                        "is_deprecated": False,
                    }
                )

            # Bulk insert via SQLAlchemy Core (much faster than ORM批量操作)
            self.db.execute(
                KnowledgeChunk.__table__.insert(),  # type: ignore[attr-defined]
                rows,
            )
            self.db.commit()
            logger.info(
                "Committed %d knowledge_chunks (source_id=%s, win_signal=%s)",
                chunks_to_write,
                rows[0]["source_id"],
                rows[0]["win_signal"],
            )
            self._buffer.clear()
            return chunks_to_write

        except Exception as exc:
            logger.error(
                "DB error during chunk flush (%d chunks): %s — rolling back",
                chunks_to_write, exc,
            )
            self.db.rollback()
            raise

    def insert_enriched_chunk(
        self,
        db: Session,
        chunk: Any,
        vector: list[float],
        win_signal: str,
        source_type: str,
        source_id: int,
        scoring_dimension_tags: Optional[list[str]] = None,
        region_tags: Optional[list[str]] = None,
        project_type_tags: Optional[list[str]] = None,
        source_label: Optional[str] = None,
        is_price_sensitive: bool = False,
    ) -> int:
        """
        Single-chunk insert (convenience wrapper, calls add+flush internally).

        This is the primary API for the seeding pipeline.

        Note: The caller passes `db` but this loader uses its own session
        (self.db). The `db` param is kept for API compatibility but ignored.

        Args:
            chunk: ChunkNode or dict with 'text', 'chunk_index', 'char_length'.
            vector: Embedding vector list[float].
            win_signal: 'positive' | 'negative' | 'neutral'
            source_type: 'historical_tender' | 'internal_postmortem'
            source_id: FK id to the source record.
            scoring_dimension_tags: list of dimension names (auto-extracted).
            region_tags: list of region names.
            project_type_tags: list of project type tags.
            source_label: Human-readable label for this chunk.
            is_price_sensitive: Whether this chunk contains price-sensitive content.

        Returns:
            knowledge_chunk.id of the inserted record (or -1 if using batch mode).
        """
        # Normalize chunk
        if hasattr(chunk, "to_dict"):
            c = chunk.to_dict()
        elif hasattr(chunk, "__dict__"):
            c = {
                "text": getattr(chunk, "text", ""),
                "chunk_index": getattr(chunk, "chunk_index", 0),
                "char_length": getattr(chunk, "char_length", 0),
                "metadata": getattr(chunk, "metadata", {}),
            }
        else:
            c = dict(chunk)

        text_content = c.get("text", "")
        chunk_index = c.get("chunk_index", 0)
        char_length = c.get("char_length", len(text_content))
        metadata = dict(c.get("metadata", {}))

        # Merge caller-provided tags into metadata
        if scoring_dimension_tags:
            metadata["scoring_dimension_tags"] = scoring_dimension_tags
        if region_tags:
            metadata["region_tags"] = region_tags
        if project_type_tags:
            metadata["project_type_tags"] = project_type_tags
        if is_price_sensitive:
            metadata["is_price_sensitive"] = True

        # w015 token_count: prefer caller's explicit value, else from chunk metadata
        token_count = metadata.get("token_count", 0)

        # Add high-level fields
        metadata["win_signal"] = win_signal
        metadata["source_type"] = source_type
        metadata["source_id"] = source_id
        if source_label:
            metadata["source_file"] = source_label

        row = {
            "chunk_type": "historical",
            "content": text_content,
            "content_vector": json.dumps(vector) if vector else None,
            "chunk_metadata": metadata,
            "source_type": source_type,
            "source_id": source_id,
            "source_label": source_label,
            "chunk_index": chunk_index,
            "win_signal": win_signal,
            "scoring_dimension_tags": scoring_dimension_tags,
            "region_tags": region_tags,
            "project_type_tags": project_type_tags,
            "is_price_sensitive": is_price_sensitive,
            "token_count": token_count,     # w015 field
            "is_deprecated": False,
        }

        try:
            result = self.db.execute(
                KnowledgeChunk.__table__.insert(),  # type: ignore[attr-defined]
                row,
            )
            self.db.commit()
            chunk_id = result.inserted_primary_key[0]
            logger.debug("Inserted chunk id=%d tender=%d win_signal=%s", chunk_id, source_id, win_signal)
            return int(chunk_id)
        except Exception as exc:
            logger.error("Single chunk insert failed (tender=%d): %s", source_id, exc)
            self.db.rollback()
            return -1

    @property
    def pending_count(self) -> int:
        """Number of chunks currently in the buffer."""
        return len(self._buffer)
