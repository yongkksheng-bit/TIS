"""Document Retriever — hybrid vector search with project-level data isolation."""
from __future__ import annotations

import math
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.week3_rag.embedder import BaseEmbedder
from app.schemas.rag import ChunkNode
from app.models.knowledge_chunk import KnowledgeChunk


class DocumentRetriever:
    """
    Hybrid retriever: converts query to vector via embedder, searches knowledge_chunks.

    CRITICAL: Every query MUST filter by project_id to prevent cross-tenant data leakage.

    Supports:
    - Production PostgreSQL/pgvector via raw SQL
    - SQLite fallback via pure Python cosine similarity
    """

    def __init__(self, db: Session, embedder: BaseEmbedder):
        self.db = db
        self.embedder = embedder

    def search(
        self,
        query: str,
        project_id: int,
        top_k: int = 5,
        chunk_type: Optional[str] = None,
    ) -> list[ChunkNode]:
        """
        Search knowledge_chunks by vector similarity, filtered by project_id.

        Args:
            query: natural language search query
            project_id: MUST filter to this project_id — ABSOLUTE REQUIREMENT
            top_k: maximum number of results to return
            chunk_type: optional filter by chunk type

        Returns:
            list of ChunkNode objects sorted by descending similarity
        """
        # Step 1: embed the query
        query_vector = self.embedder.embed_text(query)

        # Step 2: retrieve chunks (project_id filter is MANDATORY)
        chunks = self._retrieve_chunks(
            query_vector=query_vector,
            project_id=project_id,
            top_k=top_k,
            chunk_type=chunk_type,
        )

        return chunks

    def _retrieve_chunks(
        self,
        query_vector: list[float],
        project_id: int,
        top_k: int,
        chunk_type: Optional[str] = None,
    ) -> list[ChunkNode]:
        """
        Internal retrieval with project_id filter.
        Tries pgvector first (PostgreSQL), falls back to Python cosine sim (SQLite).
        """
        try:
            return self._retrieve_pgvector(query_vector, project_id, top_k, chunk_type)
        except Exception:
            # SQLite fallback
            return self._retrieve_fallback(query_vector, project_id, top_k, chunk_type)

    def _retrieve_pgvector(
        self,
        query_vector: list[float],
        project_id: int,
        top_k: int,
        chunk_type: Optional[str] = None,
    ) -> list[ChunkNode]:
        """PostgreSQL/pgvector retrieval via raw SQL."""
        query_str = json.dumps(query_vector)

        sql = text("""
            SELECT id, chunk_type, content, chunk_metadata, content_vector
            FROM knowledge_chunks
            WHERE is_deprecated = FALSE
              AND source_project_id = :project_id
              AND (:chunk_type IS NULL OR chunk_type = :chunk_type)
            ORDER BY content_vector <=> :query::vector
            LIMIT :top_k
        """)
        results = self.db.execute(sql, {
            'query': query_str,
            'project_id': project_id,
            'chunk_type': chunk_type,
            'top_k': top_k,
        }).fetchall()

        return self._rows_to_chunks(results)

    def _retrieve_fallback(
        self,
        query_vector: list[float],
        project_id: int,
        top_k: int,
        chunk_type: Optional[str] = None,
    ) -> list[ChunkNode]:
        """
        SQLite fallback: load all chunks for project, compute cosine similarity in Python.
        This bypasses pgvector but ensures TDD tests work on SQLite.
        """
        query = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.is_deprecated == False,
            KnowledgeChunk.source_project_id == project_id,
        )
        if chunk_type:
            query = query.filter(KnowledgeChunk.chunk_type == chunk_type)

        chunks = query.all()

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

        scored = []
        for chunk in chunks:
            if chunk.content_vector:
                chunk_vec = json.loads(chunk.content_vector)
                score = cosine_similarity(query_vector, chunk_vec)
                scored.append((score, chunk))

        # Sort descending by similarity, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        results = scored[:top_k]

        return [
            ChunkNode(
                text=chunk.content,
                chunk_index=0,  # original index not stored
                char_length=len(chunk.content),
                metadata=chunk.chunk_metadata or {},
            )
            for _, chunk in results
        ]

    def _rows_to_chunks(self, rows) -> list[ChunkNode]:
        """Convert SQL result rows to ChunkNode list."""
        chunks = []
        for i, row in enumerate(rows):
            metadata = row.chunk_metadata if isinstance(row.chunk_metadata, dict) else {}
            chunks.append(ChunkNode(
                text=row.content,
                chunk_index=i,
                char_length=len(row.content),
                metadata=metadata,
            ))
        return chunks
