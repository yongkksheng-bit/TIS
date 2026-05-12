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
        query_vector = self.embedder.embed_text(query)
        return self._retrieve_chunks(
            query_vector=query_vector,
            project_id=project_id,
            top_k=top_k,
            chunk_type=chunk_type,
        )

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
            ORDER BY content_vector::vector <=> CAST(:query AS vector)
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

        scored.sort(key=lambda x: x[0], reverse=True)
        results = scored[:top_k]

        return [
            ChunkNode(
                text=chunk.content,
                chunk_index=0,
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

    # ─── Dual-track retrieval (historical asset RAG) ─────────────────────────

    def retrieve_positive_samples(
        self,
        query: str,
        scoring_dimension_tags: list[str] | None = None,
        region_tags: list[str] | None = None,
        project_type: str | None = None,
        top_k: int = 5,
    ) -> list[ChunkNode]:
        """
        Retrieve win_signal='positive' chunks from historical assets.

        These represent successful bid cases to learn from.
        Results are filtered by scoring_dimension_tags, region_tags, and project_type
        when provided, to maximize relevance to the current tender.

        Args:
            query: natural language query for vector search
            scoring_dimension_tags: optional filter — only chunks tagged with these dimensions
            region_tags: optional filter — only chunks tagged with these regions
            project_type: optional filter — only chunks tagged with this project type
            top_k: maximum number of results

        Returns:
            list of ChunkNode with win_signal='positive'
        """
        query_vector = self.embedder.embed_text(query)
        return self._retrieve_historical_chunks(
            query_vector=query_vector,
            win_signal="positive",
            scoring_dimension_tags=scoring_dimension_tags,
            region_tags=region_tags,
            project_type=project_type,
            top_k=top_k,
        )

    def retrieve_negative_samples(
        self,
        query: str,
        scoring_dimension_tags: list[str] | None = None,
        region_tags: list[str] | None = None,
        project_type: str | None = None,
        loss_root_cause_tags: list[str] | None = None,
        top_k: int = 5,
    ) -> list[ChunkNode]:
        """
        Retrieve win_signal='negative' chunks from historical assets.

        These represent failure cases to avoid. Optional loss_root_cause_tags
        filter allows targeted retrieval of specific failure patterns.

        Args:
            query: natural language query for vector search
            scoring_dimension_tags: optional filter — only chunks tagged with these dimensions
            region_tags: optional filter — only chunks tagged with these regions
            project_type: optional filter — only chunks tagged with this project type
            loss_root_cause_tags: optional filter — only chunks with these loss cause tags
            top_k: maximum number of results

        Returns:
            list of ChunkNode with win_signal='negative'
        """
        query_vector = self.embedder.embed_text(query)
        return self._retrieve_historical_chunks(
            query_vector=query_vector,
            win_signal="negative",
            scoring_dimension_tags=scoring_dimension_tags,
            region_tags=region_tags,
            project_type=project_type,
            loss_root_cause_tags=loss_root_cause_tags,
            top_k=top_k,
        )

    def _retrieve_historical_chunks(
        self,
        query_vector: list[float],
        win_signal: str,
        scoring_dimension_tags: list[str] | None = None,
        region_tags: list[str] | None = None,
        project_type: str | None = None,
        loss_root_cause_tags: list[str] | None = None,
        top_k: int = 5,
    ) -> list[ChunkNode]:
        """
        Internal dual-track retrieval against knowledge_chunks with win_signal filters.

        Filters applied:
        - win_signal = 'positive' or 'negative' (REQUIRED)
        - source_type IN ('historical_tender', 'internal_postmortem') (historical assets only)
        - scoring_dimension_tags overlap (if provided)
        - region_tags overlap (if provided)
        - project_type_tags contain (if provided)
        - loss_root_cause_tags overlap (if provided, negative track only)
        """
        try:
            return self._retrieve_historical_pgvector(
                query_vector=query_vector,
                win_signal=win_signal,
                scoring_dimension_tags=scoring_dimension_tags,
                region_tags=region_tags,
                project_type=project_type,
                loss_root_cause_tags=loss_root_cause_tags,
                top_k=top_k,
            )
        except Exception:
            return self._retrieve_historical_fallback(
                query_vector=query_vector,
                win_signal=win_signal,
                scoring_dimension_tags=scoring_dimension_tags,
                region_tags=region_tags,
                project_type=project_type,
                loss_root_cause_tags=loss_root_cause_tags,
                top_k=top_k,
            )

    def _retrieve_historical_pgvector(
        self,
        query_vector: list[float],
        win_signal: str,
        scoring_dimension_tags: list[str] | None,
        region_tags: list[str] | None,
        project_type: str | None,
        loss_root_cause_tags: list[str] | None,
        top_k: int,
    ) -> list[ChunkNode]:
        """PostgreSQL/pgvector path for historical chunk retrieval."""
        query_str = json.dumps(query_vector)

        # Build tag-overlap filter conditions using PostgreSQL ARRAY && operator
        dim_filter = ""
        if scoring_dimension_tags:
            arr = ",".join(repr(t) for t in scoring_dimension_tags)
            dim_filter = f" AND scoring_dimension_tags && ARRAY[{arr}]::character varying[]"

        region_filter = ""
        if region_tags:
            arr = ",".join(repr(t) for t in region_tags)
            region_filter = f" AND region_tags && ARRAY[{arr}]::character varying[]"

        ptype_filter = ""
        if project_type:
            ptype_filter = f" AND project_type_tags && ARRAY[{repr(project_type)}]::character varying[]"

        loss_filter = ""
        if loss_root_cause_tags and win_signal == "negative":
            arr = ",".join(repr(t) for t in loss_root_cause_tags)
            loss_filter = f" AND loss_root_cause_tags && ARRAY[{arr}]::character varying[]"

        sql = text(f"""
            SELECT id, chunk_type, content, chunk_metadata, content_vector,
                   source_type, source_id, source_label, chunk_index,
                   win_signal, scoring_dimension_tags, region_tags,
                   project_type_tags, is_price_sensitive
            FROM knowledge_chunks
            WHERE is_deprecated = FALSE
              AND win_signal = :win_signal
              AND source_type IN ('historical_tender', 'internal_postmortem')
              {dim_filter}
              {region_filter}
              {ptype_filter}
              {loss_filter}
            ORDER BY content_vector::vector <=> CAST(:query AS vector)
            LIMIT :top_k
        """)

        params: dict = {
            "query": query_str,
            "win_signal": win_signal,
            "top_k": top_k,
        }

        results = self.db.execute(sql, params).fetchall()
        return self._rows_to_historical_chunks(results)

    def _retrieve_historical_fallback(
        self,
        query_vector: list[float],
        win_signal: str,
        scoring_dimension_tags: list[str] | None,
        region_tags: list[str] | None,
        project_type: str | None,
        loss_root_cause_tags: list[str] | None,
        top_k: int,
    ) -> list[ChunkNode]:
        """SQLite/pure-Python fallback for historical chunk retrieval."""
        query = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.is_deprecated == False,
            KnowledgeChunk.win_signal == win_signal,
            KnowledgeChunk.source_type.in_(["historical_tender", "internal_postmortem"]),
        )

        chunks = query.all()

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

        scored = []
        for chunk in chunks:
            if scoring_dimension_tags:
                chunk_dims = list(chunk.scoring_dimension_tags) if chunk.scoring_dimension_tags else []
                if not any(d in chunk_dims for d in scoring_dimension_tags):
                    continue
            if region_tags:
                chunk_regions = list(chunk.region_tags) if chunk.region_tags else []
                if not any(r in chunk_regions for r in region_tags):
                    continue
            if project_type:
                chunk_ptypes = list(chunk.project_type_tags) if chunk.project_type_tags else []
                if project_type not in chunk_ptypes:
                    continue
            if loss_root_cause_tags and win_signal == "negative":
                chunk_loss = list(getattr(chunk, "loss_root_cause_tags", []) or [])
                if not any(l in chunk_loss for l in loss_root_cause_tags):
                    continue

            if chunk.content_vector:
                chunk_vec = json.loads(chunk.content_vector)
                score = cosine_similarity(query_vector, chunk_vec)
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = scored[:top_k]

        return [
            ChunkNode(
                text=chunk.content,
                chunk_index=getattr(chunk, "chunk_index", 0),
                char_length=len(chunk.content),
                metadata={
                    "win_signal": chunk.win_signal,
                    "scoring_dimension_tags": list(chunk.scoring_dimension_tags) if chunk.scoring_dimension_tags else [],
                    "region_tags": list(chunk.region_tags) if chunk.region_tags else [],
                    "project_type_tags": list(chunk.project_type_tags) if chunk.project_type_tags else [],
                    "source_label": getattr(chunk, "source_label", ""),
                    "source_type": chunk.source_type,
                },
            )
            for _, chunk in results
        ]

    def _rows_to_historical_chunks(self, rows) -> list[ChunkNode]:
        """Convert SQL result rows to ChunkNode with full historical metadata."""
        chunks = []
        for row in rows:
            chunks.append(ChunkNode(
                text=row.content,
                chunk_index=getattr(row, "chunk_index", 0),
                char_length=len(row.content),
                metadata={
                    "win_signal": getattr(row, "win_signal", None),
                    "scoring_dimension_tags": list(getattr(row, "scoring_dimension_tags") or []),
                    "region_tags": list(getattr(row, "region_tags") or []),
                    "project_type_tags": list(getattr(row, "project_type_tags") or []),
                    "source_label": getattr(row, "source_label", ""),
                    "source_type": getattr(row, "source_type", None),
                },
            ))
        return chunks
