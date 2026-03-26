# Week 3 Implementation Plan: RAG + 双模式技术标生成引擎

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现技术标的智能生成（RAG 检索 + LLM 生成）与模式分流（AUTO/GUIDED）。Week 2 专员审批后锁定 generation_mode，本周实现"无内幕极致优化"和"有内幕定制化"两套完整 Pipeline。

**Architecture:** RAG 管道拆分为 5 个独立组件（Chunker → Embedding → Retriever → PromptBuilder → Generator），通过 SQLAlchemy + pgvector 存储向量数据，所有 LLM 调用在测试中 Mock。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pgvector, DeepSeek API (Mocked in tests), Pydantic

**Key Constraints from Master Spec §5.2:**
- `generation_mode` 在 Week 2 专员审批时锁定（APPROVED_BY_SPECIALIST 时写入 Project 表）
- AUTO 模式：top_k=5，低价超越策略，温度 0.7
- GUIDED 模式：top_k=3，专员内幕要点，温度 0.5
- 向量检索阈值：cosine similarity ≥ 0.75

---

## File Structure

```
app/models/
  knowledge_chunk.py         # KnowledgeChunk SQLAlchemy model
  tech_proposal.py           # TechProposalTask, ScoringIndex, GenerationLog models

app/core/week3_rag/
  text_chunker.py            # Splits tender docs into semantic chunks
  embedding_service.py        # DeepSeek embedding API wrapper + storage
  hybrid_retriever.py         # Vector search + metadata filtering + weighted ranking
  prompt_builder.py           # Mode-aware prompt assembly (AUTO vs GUIDED)
  llm_mock.py                 # Mock LLM for TDD (never real API calls)
  tech_proposal_generator.py  # Main orchestrator: Chunker → Retriever → PromptBuilder → LLM

app/schemas/
  week3.py                   # Pydantic schemas for Week 3 API

app/api/v1/endpoints/
  tech_proposals.py          # FastAPI router for Week 3 endpoints

alembic/versions/
  w003_add_week3_tables.py   # Migration: knowledge_chunks, tech_proposal_tasks,
                              # scoring_indexes, generation_logs + pgvector index

tests/week3/
  test_text_chunker.py       # TDD: chunking logic
  test_embedding_service.py   # TDD: embedding storage/retrieval (mocked)
  test_hybrid_retriever.py   # TDD: retrieval with filters
  test_prompt_builder.py     # TDD: AUTO vs GUIDED prompt differences
  test_llm_mock.py            # TDD: mock LLM response validation
  test_tech_proposal_generator.py  # TDD: full pipeline with mocked LLM
  test_api_tech_proposals.py  # TestClient API tests
```

---

## Task 1: Database Migration (w003) + KnowledgeChunk Model

**Files:**
- Create: `alembic/versions/w003_add_week3_tables.py`
- Create: `app/models/knowledge_chunk.py`
- Create: `app/models/tech_proposal.py`

- [ ] **Step 1: Write the migration `w003_add_week3_tables.py`**

```python
"""Week 3 tables: knowledge_chunks, tech_proposal_tasks, scoring_indexes, generation_logs

Revision ID: w003
Revises: w002
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, ARRAY

revision = 'w003'
down_revision = 'w002'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # knowledge_chunks (with pgvector)
    op.create_table('knowledge_chunks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('chunk_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        # pgvector column - use Text as fallback since not all DBs have pgvector
        sa.Column('content_vector', sa.Text(), nullable=True),
        sa.Column('metadata', JSON, nullable=False, default={}),
        sa.Column('source_project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=True),
        sa.Column('is_deprecated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_knowledge_vector', 'knowledge_chunks', ['content_vector'])

    # tech_proposal_tasks
    op.create_table('tech_proposal_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('generation_mode', sa.String(20), nullable=False),
        sa.Column('input_config', JSON, nullable=False, default={}),
        sa.Column('generated_content', JSON, nullable=True),
        sa.Column('final_content', sa.Text(), nullable=True),
        sa.Column('editor_version', sa.Integer(), default=1),
        sa.Column('status', sa.String(20), default='generating'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('confirmed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # scoring_indexes
    op.create_table('scoring_indexes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score_item_name', sa.String(255), nullable=False),
        sa.Column('score_weight', sa.Numeric(5, 2), nullable=False),
        sa.Column('corresponding_section_id', sa.Integer(), nullable=True),
        sa.Column('corresponding_section_title', sa.String(255), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('keyword_matches', JSON, nullable=True),
        sa.Column('is_fully_responded', sa.Boolean(), default=False),
        sa.Column('evidence_paragraph_ids', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # generation_logs
    op.create_table('generation_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tech_proposal_tasks.id'), nullable=True),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=True),
        sa.Column('prompt_used', sa.Text(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(8, 4), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table('generation_logs')
    op.drop_table('scoring_indexes')
    op.drop_table('tech_proposal_tasks')
    op.drop_table('knowledge_chunks')
```

- [ ] **Step 2: Run migration test**

Run: `pytest tests/week2/test_week2_migrations.py -v` (existing should still pass)
Expected: All pass

- [ ] **Step 3: Write SQLAlchemy models**

```python
# app/models/knowledge_chunk.py
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import Base, TimestampMixin

class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_vector: Mapped[str] = mapped_column(Text, nullable=True)  # serialized vector
    metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    source_project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
```

```python
# app/models/tech_proposal.py
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON
from app.models.base import Base, TimestampMixin

class TechProposalTask(Base, TimestampMixin):
    __tablename__ = "tech_proposal_tasks"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    input_config: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    generated_content: Mapped[dict] = mapped_column(JSON, nullable=True)
    final_content: Mapped[str] = mapped_column(Text, nullable=True)
    editor_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default='generating')
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

class ScoringIndex(Base):
    __tablename__ = "scoring_indexes"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    score_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    score_weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    corresponding_section_id: Mapped[int] = mapped_column(Integer, nullable=True)
    corresponding_section_title: Mapped[str] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=True)
    keyword_matches: Mapped[list] = mapped_column(JSON, nullable=True)
    is_fully_responded: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_paragraph_ids: Mapped[list] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=sa.func.now())

class GenerationLog(Base):
    __tablename__ = "generation_logs"

    task_id: Mapped[int] = mapped_column(ForeignKey("tech_proposal_tasks.id"), nullable=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    section_id: Mapped[int] = mapped_column(Integer, nullable=True)
    prompt_used: Mapped[str] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=sa.func.now())
```

- [ ] **Step 4: Run tests to verify models work**

Run: `python -c "from app.models.knowledge_chunk import KnowledgeChunk; from app.models.tech_proposal import TechProposalTask; print('models OK')"`
Expected: No import errors

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/w003_add_week3_tables.py app/models/knowledge_chunk.py app/models/tech_proposal.py
git commit -m "feat(week3): add Week 3 database migration and models for RAG pipeline"
```

---

## Task 2: Text Chunker

**Files:**
- Create: `app/core/week3_rag/text_chunker.py`
- Create: `tests/week3/test_text_chunker.py`

- [ ] **Step 1: Write failing test**

```python
# tests/week3/test_text_chunker.py
import pytest
from app.core.week3_rag.text_chunker import TextChunker

class TestTextChunker:
    def test_split_by_paragraph(self):
        """Long document splits into chunks of ~500 chars."""
        text = "\n\n".join([f"段落{i}: " + "x" * 200 for i in range(10)])
        chunks = TextChunker(max_chars=500).chunk(text)
        assert len(chunks) > 1
        assert all(len(c) <= 550 for c in chunks)  # 10% overhead

    def test_chunk_includes_metadata(self):
        """Each chunk carries source section info."""
        text = "第一章：概述\n\n内容内容"
        chunks = TextChunker(max_chars=500).chunk(text)
        assert all('section_title' in c for c in chunks)

    def test_short_text_returns_single_chunk(self):
        """Short document returns as single chunk."""
        text = "这是一段很短的内容"
        chunks = TextChunker(max_chars=500).chunk(text)
        assert len(chunks) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/week3/test_text_chunker.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal TextChunker**

```python
# app/core/week3_rag/text_chunker.py
"""Text Chunker - splits tender documents into semantic chunks for RAG."""

class TextChunker:
    """
    Splits large text into overlapping semantic chunks for embedding.

    Rules:
    - Split on paragraph boundaries (\n\n) when possible
    - Target chunk size: max_chars (default 500 chars)
    - Preserve section headers as chunk metadata
    - Overlap: 50 chars between chunks to maintain context
    """

    def __init__(self, max_chars: int = 500, overlap: int = 50):
        self.max_chars = max_chars
        self.overlap = overlap

    def chunk(self, text: str) -> list[dict]:
        """
        Split text into chunks.

        Returns list of dicts:
            [{'content': str, 'section_title': str, 'chunk_index': int}, ...]
        """
        if not text or len(text.strip()) == 0:
            return []

        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        current_section = "未分类"
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Detect section header (short line followed by newline)
            lines = para.split("\n")
            if len(lines) > 0 and len(lines[0]) < 60 and len(lines[0]) < len(para) * 0.3:
                current_section = lines[0].strip()

            if len(current) + len(para) + 2 <= self.max_chars:
                current += ("\n\n" if current else "") + para
            else:
                if current:
                    chunks.append({
                        'content': current,
                        'section_title': current_section,
                        'chunk_index': chunk_index
                    })
                    chunk_index += 1
                    # Start new chunk with overlap
                    current = para[-self.overlap:] + "\n\n" + para if len(para) > self.overlap else para
                else:
                    # Single paragraph exceeds max_chars, force split
                    chunks.append({
                        'content': para[:self.max_chars],
                        'section_title': current_section,
                        'chunk_index': chunk_index
                    })
                    chunk_index += 1
                    current = para[self.overlap:] if len(para) > self.overlap else ""

        if current:
            chunks.append({
                'content': current,
                'section_title': current_section,
                'chunk_index': chunk_index
            })

        return chunks
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/week3/test_text_chunker.py -v`
Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/week3_rag/text_chunker.py tests/week3/test_text_chunker.py
git commit -m "feat(week3): add TextChunker for semantic document splitting"
```

---

## Task 3: Embedding Service + Mock LLM

**Files:**
- Create: `app/core/week3_rag/embedding_service.py`
- Create: `app/core/week3_rag/llm_mock.py`
- Create: `tests/week3/test_embedding_service.py`
- Create: `tests/week3/test_llm_mock.py`

- [ ] **Step 1: Write failing tests for embedding service**

```python
# tests/week3/test_embedding_service.py
import pytest
from unittest.mock import MagicMock, patch
from app.core.week3_rag.embedding_service import EmbeddingService
from app.core.week3_rag.llm_mock import MockDeepSeekLLM

class TestEmbeddingService:
    def test_embed_text_returns_vector(self):
        """Embedding service calls API and returns vector."""
        with patch('app.core.week3_rag.embedding_service.get_embedding_api') as mock:
            mock.return_value = [0.1] * 1536  # fake 1536-dim vector
            service = EmbeddingService()
            result = service.embed("测试文本")
            assert len(result) == 1536
            assert all(isinstance(v, float) for v in result)

    def test_store_chunk_saves_to_db(self, db_session):
        """Store embedded chunk in knowledge_chunks table."""
        with patch('app.core.week3_rag.embedding_service.get_embedding_api') as mock:
            mock.return_value = [0.1] * 1536
            service = EmbeddingService(db_session)
            chunk_id = service.store_chunk(
                content="冷链配送方案",
                chunk_type="technical_solution",
                metadata={"owner_type": "school"}
            )
            assert chunk_id is not None

    def test_retrieve_top_k_returns_chunks(self, db_session):
        """Retrieve top-k similar chunks by vector similarity."""
        service = EmbeddingService(db_session)
        results = service.retrieve(query_vector=[0.1]*1536, top_k=3)
        assert len(results) <= 3
        assert all('content' in r and 'distance' in r for r in results)
```

```python
# tests/week3/test_llm_mock.py
import pytest
from app.core.week3_rag.llm_mock import MockDeepSeekLLM, MockResponse

class TestMockDeepSeekLLM:
    def test_generate_returns_consistent_format(self):
        """Mock LLM always returns a dict with content and usage."""
        mock = MockDeepSeekLLM()
        response = mock.generate("写一个配送方案")
        assert 'content' in response
        assert 'usage' in response
        assert len(response['content']) > 0

    def test_guided_mode_respects_constraints(self):
        """GUIDED mode prompt must include the insider_notes."""
        mock = MockDeepSeekLLM()
        response = mock.generate(
            prompt="写配送方案",
            mode="guided",
            insider_notes=["必须使用双汇品牌", "避开高峰时段"]
        )
        # Mock just echoes back, but the call should include the notes in log
        assert response['content'] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/week3/test_embedding_service.py tests/week3/test_llm_mock.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write EmbeddingService**

```python
# app/core/week3_rag/embedding_service.py
"""Embedding Service - DeepSeek embedding API wrapper + pgvector storage."""
import os
import json
from typing import Optional
from sqlalchemy.orm import Session
from app.models.knowledge_chunk import KnowledgeChunk

class EmbeddingService:
    """
    Handles text embedding via DeepSeek API and storage in PostgreSQL/pgvector.

    In production: calls DeepSeek embedding API
    In tests: uses MockDeepSeekLLM
    """

    def __init__(self, db: Session):
        self.db = db
        self._embedding_api = None  # lazy load

    def _get_embedding_api(self):
        """Lazy-load the embedding API (DeepSeek or mock for tests)."""
        if self._embedding_api is None:
            # In tests, this will be patched. In prod, use real API.
            from app.core.week3_rag.llm_mock import get_embedding_model
            self._embedding_api = get_embedding_model()
        return self._embedding_api

    def embed(self, text: str) -> list[float]:
        """Get embedding vector for text."""
        api = self._get_embedding_api()
        return api.embed(text)

    def store_chunk(
        self,
        content: str,
        chunk_type: str,
        metadata: dict,
        source_project_id: Optional[int] = None
    ) -> int:
        """Embed content and store in knowledge_chunks table."""
        vector = self.embed(content)
        chunk = KnowledgeChunk(
            chunk_type=chunk_type,
            content=content,
            content_vector=json.dumps(vector),
            metadata=metadata,
            source_project_id=source_project_id,
            is_deprecated=False
        )
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk.id

    def retrieve(
        self,
        query_vector: list[float],
        top_k: int = 5,
        chunk_type: Optional[str] = None,
        owner_type: Optional[str] = None,
        min_distance: float = 0.3
    ) -> list[dict]:
        """
        Retrieve top-k chunks by cosine similarity.

        Uses pgvector via raw SQL (pgvector extension required in PostgreSQL).
        Falls back to simple JSON storage when pgvector not available.
        """
        query_str = json.dumps(query_vector)

        # Try pgvector query first (production)
        try:
            from sqlalchemy import text
            sql = text("""
                SELECT id, content, metadata, content_vector,
                       (content_vector <=> :query::vector) as distance
                FROM knowledge_chunks
                WHERE is_deprecated = FALSE
                  AND (:chunk_type IS NULL OR chunk_type = :chunk_type)
                  AND (:owner_type IS NULL OR metadata->>'owner_type' = :owner_type)
                ORDER BY content_vector <=> :query::vector
                LIMIT :top_k
            """)
            results = self.db.execute(sql, {
                'query': query_str,
                'chunk_type': chunk_type,
                'owner_type': owner_type,
                'top_k': top_k
            }).fetchall()

            chunks = []
            for row in results:
                if row.distance < min_distance:
                    chunks.append({
                        'id': row.id,
                        'content': row.content,
                        'metadata': row.metadata,
                        'distance': row.distance
                    })
            return chunks
        except Exception:
            # Fallback: simple JSON-based vector comparison
            return self._retrieve_fallback(query_vector, top_k, chunk_type, owner_type, min_distance)

    def _retrieve_fallback(
        self, query_vector: list[float], top_k: int,
        chunk_type: str, owner_type: str, min_distance: float
    ) -> list[dict]:
        """Fallback retrieval using cosine similarity in Python."""
        import math

        chunks = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.is_deprecated == False
        ).all()

        def cosine_sim(a, b):
            dot = sum(x*y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x*x for x in a))
            norm_b = math.sqrt(sum(x*x for x in b))
            return dot / (norm_a * norm_b) if norm_a and norm_b else 0

        scored = []
        for chunk in chunks:
            if chunk_type and chunk.chunk_type != chunk_type:
                continue
            if owner_type and chunk.metadata.get('owner_type') != owner_type:
                continue
            vec = json.loads(chunk.content_vector) if chunk.content_vector else [0]*1536
            dist = 1 - cosine_sim(query_vector, vec)
            if dist < min_distance:
                scored.append({
                    'id': chunk.id,
                    'content': chunk.content,
                    'metadata': chunk.metadata,
                    'distance': dist
                })

        scored.sort(key=lambda x: x['distance'])
        return scored[:top_k]
```

```python
# app/core/week3_rag/llm_mock.py
"""Mock LLM for TDD - never makes real API calls."""

import json
from typing import Optional
from dataclasses import dataclass

@dataclass
class MockResponse:
    content: str
    usage: dict

class MockDeepSeekLLM:
    """
    Mock LLM that returns deterministic responses for tests.
    NEVER makes real DeepSeek API calls in tests.
    """

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.call_history = []

    def generate(
        self,
        prompt: str,
        mode: str = "auto",
        insider_notes: Optional[list[str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> MockResponse:
        """
        Mock generate - records call, returns deterministic fake response.
        """
        self.call_history.append({
            'prompt': prompt,
            'mode': mode,
            'insider_notes': insider_notes,
            'temperature': temperature
        })

        # Deterministic fake response based on mode
        if mode == "guided" and insider_notes:
            content = f"【定制化方案】基于内幕要求生成：{', '.join(insider_notes)}。\n\n本方案严格遵循以上要求，展示了高度定制化特点。"
        else:
            content = (
                "【响应评分项：配送方案】\n\n"
                "针对本项目配送需求，我方承诺实现12小时极速配送服务，并建立2小时应急响应机制。\n\n"
                "【本项目优势】\n"
                "1. 类似XX学校项目经验（2024年配送准时率100%）\n"
                "2. 冷链设备投入500万保障全程温控\n"
                "3. 应急预案完善，已通过ISO9001认证"
            )

        return MockResponse(
            content=content,
            usage={'input_tokens': 500, 'output_tokens': 300, 'cost_usd': 0.002}
        )

    def embed(self, text: str) -> list[float]:
        """Mock embedding - returns deterministic pseudo-random vector."""
        import hashlib
        # Deterministic 1536-dim vector from text hash
        h = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(1536):
            vec.append((h[i % len(h)] / 255.0) * 2 - 1)  # -1 to 1 range
        return vec


# Module-level function for dependency injection
def get_embedding_model() -> MockDeepSeekLLM:
    return MockDeepSeekLLM()


def get_llm() -> MockDeepSeekLLM:
    return MockDeepSeekLLM()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/week3/test_embedding_service.py tests/week3/test_llm_mock.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/week3_rag/embedding_service.py app/core/week3_rag/llm_mock.py tests/week3/test_embedding_service.py tests/week3/test_llm_mock.py
git commit -m "feat(week3): add EmbeddingService with pgvector storage and MockDeepSeekLLM for TDD"
```

---

## Task 4: Hybrid Retriever

**Files:**
- Create: `app/core/week3_rag/hybrid_retriever.py`
- Create: `tests/week3/test_hybrid_retriever.py`

- [ ] **Step 1: Write failing test**

```python
# tests/week3/test_hybrid_retriever.py
import pytest
from app.core.week3_rag.hybrid_retriever import HybridRetriever
from app.core.week3_rag.llm_mock import MockDeepSeekLLM

class TestHybridRetriever:
    def test_retrieve_filters_by_metadata(self):
        """Owner type filter should be applied."""
        retriever = HybridRetriever()
        results = retriever.retrieve(
            query="冷链配送方案",
            project_context={'owner_type': 'school', 'service_type': 'food_delivery'},
            top_k=5
        )
        # Results should have owner_type match or distance cutoff
        for r in results:
            if r.get('metadata', {}).get('owner_type'):
                assert r['metadata']['owner_type'] in ['school', None]

    def test_retrieve_respects_min_similarity(self):
        """Similarity < 0.75 (distance > 0.25) should be filtered."""
        retriever = HybridRetriever()
        results = retriever.retrieve(
            query="完全不相关的查询 xyzabc",
            project_context={},
            top_k=5
        )
        assert all(r['distance'] < 0.25 for r in results)

    def test_guided_mode_uses_tighter_retrieval(self):
        """GUIDED mode should retrieve fewer, more precise chunks (top_k=3)."""
        retriever = HybridRetriever()
        results = retriever.retrieve(
            query="品牌要求：双汇",
            project_context={'owner_type': 'school'},
            mode='guided',
            top_k=3
        )
        assert len(results) <= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/week3/test_hybrid_retriever.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write HybridRetriever**

```python
# app/core/week3_rag/hybrid_retriever.py
"""Hybrid Retriever - combines vector search + metadata filtering + business rules."""
from typing import Optional
from sqlalchemy.orm import Session
from app.core.week3_rag.embedding_service import EmbeddingService
from app.core.week3_rag.llm_mock import get_embedding_model

class HybridRetriever:
    """
    Hybrid retrieval: vector similarity + metadata filtering + weighted ranking.

    Per Week 3 spec:
    - AUTO mode: top_k=5, cosine threshold 0.75 (distance < 0.25)
    - GUIDED mode: top_k=3, stricter filtering on insider tags
    - Weights: distance*0.6 + quality_score*0.3 + usage_count*0.1
    """

    SIMILARITY_THRESHOLD = 0.75  # cosine similarity minimum

    def __init__(self, db: Session):
        self.db = db
        self.embedding_service = EmbeddingService(db)

    def retrieve(
        self,
        query: str,
        project_context: dict,
        mode: str = "auto",
        top_k: Optional[int] = None
    ) -> list[dict]:
        """
        Retrieve relevant knowledge chunks for a query.

        Args:
            query: Natural language query
            project_context: Dict with owner_type, service_type, score_point, etc.
            mode: 'auto' or 'guided'
            top_k: Override default top_k (auto=5, guided=3)

        Returns:
            List of dicts: [{'id', 'content', 'metadata', 'distance'}, ...]
        """
        top_k = top_k or (3 if mode == "guided" else 5)
        min_distance = 1.0 - self.SIMILARITY_THRESHOLD  # 0.25

        # Get query embedding
        query_vector = self.embedding_service.embed(query)

        # Extract filters from context
        owner_type = project_context.get('owner_type')
        service_type = project_context.get('service_type')
        chunk_type = project_context.get('chunk_type')  # e.g., 'technical_solution'

        # Retrieve from vector store
        results = self.embedding_service.retrieve(
            query_vector=query_vector,
            top_k=top_k * 2,  # over-retrieve for re-ranking
            chunk_type=chunk_type,
            owner_type=owner_type,
            min_distance=min_distance
        )

        # Apply business rules: quality_score + usage_count re-ranking
        reranked = self._rerank(results, project_context)

        return reranked[:top_k]

    def _rerank(self, results: list[dict], project_context: dict) -> list[dict]:
        """Re-rank retrieved chunks by quality_score and usage_count."""
        service_type = project_context.get('service_type')

        def score_weight(r: dict) -> float:
            meta = r.get('metadata', {})
            quality = float(meta.get('quality_score', 50))
            usage = float(meta.get('usage_count', 0))

            # Normalize: quality 0-100 → 0-1, usage 0-100+ → 0-1
            quality_norm = quality / 100.0
            usage_norm = min(usage / 100.0, 1.0)

            # Weighted composite: distance already 0-1, quality 0-1, usage 0-1
            distance_weight = r['distance']
            quality_weight = (1.0 - quality_norm) * 0.3  # lower quality = higher weight
            usage_weight = (1.0 - usage_norm) * 0.1  # lower usage = higher weight

            composite = distance_weight * 0.6 + quality_weight + usage_weight
            return composite

        results.sort(key=score_weight)
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/week3/test_hybrid_retriever.py -v`
Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/week3_rag/hybrid_retriever.py tests/week3/test_hybrid_retriever.py
git commit -m "feat(week3): add HybridRetriever with metadata filtering and re-ranking"
```

---

## Task 5: Prompt Builder (Mode-Aware)

**Files:**
- Create: `app/core/week3_rag/prompt_builder.py`
- Create: `tests/week3/test_prompt_builder.py`

- [ ] **Step 1: Write failing test**

```python
# tests/week3/test_prompt_builder.py
import pytest
from app.core.week3_rag.prompt_builder import PromptBuilder

class TestPromptBuilder:
    def test_auto_mode_prompt_has_ABCD_strategies(self):
        """AUTO mode prompt must include A/B/C/D strategy instructions."""
        builder = PromptBuilder()
        prompt = builder.build_auto_prompt(
            scoring_item={'name': '配送方案', 'weight': 20, 'description': '响应配送要求'},
            contexts=[{'content': '参考方案', 'metadata': {'quality_score': 80}}],
            owner_type='school'
        )
        assert 'A.' in prompt or '差异化' in prompt
        assert 'B.' in prompt or '证据链' in prompt
        assert 'C.' in prompt or '评分点响应' in prompt
        assert 'D.' in prompt or '语境' in prompt

    def test_guided_mode_prompt_includes_insider_notes(self):
        """GUIDED mode must embed insider_notes verbatim."""
        builder = PromptBuilder()
        prompt = builder.build_guided_prompt(
            scoring_item={'name': '配送方案', 'weight': 20, 'description': '响应配送要求'},
            insider_notes=['必须使用双汇品牌', '避开高峰时段'],
            contexts=[{'content': '参考方案'}],
            owner_type='school'
        )
        assert '双汇' in prompt
        assert '避开高峰时段' in prompt
        assert '内幕' in prompt or '定制化' in prompt

    def test_auto_mode_uses_high_temperature(self):
        """AUTO mode prompt specifies temperature=0.7."""
        builder = PromptBuilder()
        config = builder.get_generation_config('auto')
        assert config['temperature'] == 0.7

    def test_guided_mode_uses_low_temperature(self):
        """GUIDED mode prompt specifies temperature=0.5."""
        builder = PromptBuilder()
        config = builder.get_generation_config('guided')
        assert config['temperature'] == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/week3/test_prompt_builder.py -v`
Expected: FAIL

- [ ] **Step 3: Write PromptBuilder**

```python
# app/core/week3_rag/prompt_builder.py
"""Prompt Builder - mode-aware prompt assembly for AUTO vs GUIDED generation."""

from typing import Optional

class PromptBuilder:
    """
    Builds LLM prompts based on generation mode (AUTO/GUIDED).

    AUTO mode: ABCD strategies for maximum differentiation (temperature=0.7)
    GUIDED mode: Insider-notes-constrained generation (temperature=0.5)
    """

    OWNER_TONE = {
        'school': {
            'emphasis': '"守护师生健康"、"营养安全"、"家校共育"',
            'tone': '亲切专业，有教育情怀和温度'
        },
        'government': {
            'emphasis': '"规范严谨"、"合规溯源"、"应急保障"',
            'tone': '正式规范，多用政策术语和量化指标'
        },
        'hospital': {
            'emphasis': '"医疗级标准"、"院感控制"、"药品安全"',
            'tone': '严谨专业，强调合规和安全'
        },
        'enterprise': {
            'emphasis': '"效率最优"、"成本控制"、"市场竞争"',
            'tone': '商业化、务实高效'
        }
    }

    def build_auto_prompt(
        self,
        scoring_item: dict,
        contexts: list[dict],
        owner_type: str
    ) -> str:
        """
        Build AUTO mode prompt with ABCD optimization strategies.
        """
        tone = self.OWNER_TONE.get(owner_type, self.OWNER_TONE['enterprise'])

        contexts_text = "\n\n---\n\n".join([
            f"参考方案 {i+1}（质量分{r['metadata'].get('quality_score', '?')}）：\n{r['content']}"
            for i, r in enumerate(contexts)
        ]) if contexts else "（无高质量历史参考，使用通用模板）"

        return f"""【任务】撰写技术方案响应评分项「{scoring_item['name']}」（分值：{scoring_item['weight']}分）

【评分标准要求】
{scoring_item['description']}

【历史优秀方案参考】
{contexts_text}

【优化策略 - 必须严格执行】

A. 差异化超越：如果标准要求24小时配送，你承诺12小时+2小时应急预备；如果要求95%达标率，你承诺99%并提供惩罚机制

B. 证据链完整：每个承诺都要有具体数据、流程图描述、检查表支撑，引用过往成功案例（格式："如XX学校2024年配送准时率100%"）

C. 专家评审友好：使用【评分点响应】格式开头，使用加粗、表格、项目符号，确保专家一眼看到对应关系

D. 业主语境适配：{tone['emphasis']}，语言有{tone['tone']}

【输出格式】
1. 开头标记：【响应评分项：{scoring_item['name']}】
2. 方案正文：800-1200字，包含：现状分析→方案设计→保障措施→应急预案
3. 证据链小节：【本项目优势】列举3条与历史案例的对应优势

直接输出正文，不要解释。"""

    def build_guided_prompt(
        self,
        scoring_item: dict,
        insider_notes: list[str],
        contexts: list[dict],
        owner_type: str
    ) -> str:
        """
        Build GUIDED mode prompt with insider notes constraints.
        """
        tone = self.OWNER_TONE.get(owner_type, self.OWNER_TONE['enterprise'])

        insider_text = "\n".join([f"- {note}" for note in insider_notes])
        contexts_text = "\n\n".join([r['content'] for r in contexts]) if contexts else "（无相关历史参考）"

        return f"""【定制化方案生成 - 有内幕关系项目】

【业主特殊要求 - 必须严格遵守】
{insider_text}

【评分项要求】
{scoring_item['description']}

【历史参考（仅作格式参考，内容必须符合上述特殊要求）】
{contexts_text}

【生成要求】
1. 严格体现业主特殊要求（如指定品牌、特定时段、特殊流程）
2. 不得使用通用模板语言，必须提及业主的具体要求
3. 语气：{tone['tone']}

【输出格式】
1. 开头标记：【响应评分项：{scoring_item['name']}】（定制化版）
2. 方案正文：800-1200字
3. 定制化亮点小节：【内幕要求满足情况】逐一对应上述特殊要求

直接输出正文，不要解释。"""

    def get_generation_config(self, mode: str) -> dict:
        """Return LLM generation config for given mode."""
        if mode == "guided":
            return {
                'temperature': 0.5,
                'max_tokens': 2000,
                'model': 'deepseek-chat'
            }
        return {
            'temperature': 0.7,
            'max_tokens': 2000,
            'model': 'deepseek-chat'
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/week3/test_prompt_builder.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/week3_rag/prompt_builder.py tests/week3/test_prompt_builder.py
git commit -m "feat(week3): add PromptBuilder with AUTO ABCD strategies and GUIDED insider-notes mode"
```

---

## Task 6: TechProposalGenerator (Orchestrator)

**Files:**
- Create: `app/core/week3_rag/tech_proposal_generator.py`
- Create: `tests/week3/test_tech_proposal_generator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/week3/test_tech_proposal_generator.py
import pytest
from unittest.mock import MagicMock, patch
from app.core.week3_rag.tech_proposal_generator import TechProposalGenerator
from app.core.week3_rag.llm_mock import MockDeepSeekLLM

class TestTechProposalGenerator:
    def test_auto_mode_generates_full_pipeline(self):
        """AUTO mode: retrieve → prompt → LLM → result dict."""
        with patch('app.core.week3_rag.embedding_service.get_embedding_model') as mock_emb, \
             patch('app.core.week3_rag.llm_mock.get_llm') as mock_llm:
            mock_emb.return_value = MockDeepSeekLLM()
            mock_llm.return_value = MockDeepSeekLLM()

            generator = TechProposalGenerator(db_session)
            result = generator.generate_section(
                project_id=1,
                scoring_item={'name': '配送方案', 'weight': 20, 'description': '配送要求'},
                mode='auto'
            )

            assert 'section_title' in result
            assert 'content' in result
            assert 'source_chunks' in result
            assert 'generation_timestamp' in result

    def test_guided_mode_requires_insider_notes(self):
        """GUIDED mode without insider_notes raises ValueError."""
        with patch('app.core.week3_rag.embedding_service.get_embedding_model') as mock_emb, \
             patch('app.core.week3_rag.llm_mock.get_llm') as mock_llm:
            mock_emb.return_value = MockDeepSeekLLM()
            mock_llm.return_value = MockDeepSeekLLM()

            generator = TechProposalGenerator(db_session)
            with pytest.raises(ValueError, match="内幕"):
                generator.generate_section(
                    project_id=1,
                    scoring_item={'name': '配送方案', 'weight': 20},
                    mode='guided',
                    insider_notes=[]
                )

    def test_generation_log_created(self, db_session):
        """Each generation creates a GenerationLog entry."""
        # Verify log_count before and after
        ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/week3/test_tech_proposal_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Write TechProposalGenerator**

```python
# app/core/week3_rag/tech_proposal_generator.py
"""Tech Proposal Generator - main orchestrator for Week 3 RAG pipeline."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from app.models.tech_proposal import TechProposalTask, ScoringIndex, GenerationLog
from app.models.project import Project
from app.core.week3_rag.hybrid_retriever import HybridRetriever
from app.core.week3_rag.prompt_builder import PromptBuilder
from app.core.week3_rag.llm_mock import get_llm

class TechProposalGenerator:
    """
    Orchestrates the full RAG → LLM generation pipeline.

    Pipeline:
    1. Retrieve relevant knowledge chunks (HybridRetriever)
    2. Build mode-specific prompt (PromptBuilder)
    3. Generate with LLM (MockDeepSeekLLM in tests, real DeepSeek in prod)
    4. Log generation (GenerationLog)
    5. Return structured result
    """

    def __init__(self, db: Session):
        self.db = db
        self.retriever = HybridRetriever(db)
        self.prompt_builder = PromptBuilder()

    def generate_section(
        self,
        project_id: int,
        scoring_item: dict,
        mode: str,
        insider_notes: Optional[list[str]] = None
    ) -> dict:
        """
        Generate a single technical proposal section.

        Args:
            project_id: Project ID
            scoring_item: Dict with name, weight, description
            mode: 'auto' or 'guided'
            insider_notes: Required for guided mode

        Returns:
            Dict: {section_title, content, source_chunks, linked_cases, ai_rewrite_count, generation_timestamp}
        """
        # Validate mode
        if mode not in ('auto', 'guided'):
            raise ValueError(f"Unknown mode: {mode}")

        if mode == 'guided' and not insider_notes:
            raise ValueError("GUIDED mode requires insider_notes")

        # Get project context for retrieval
        project = self.db.get(Project, project_id)
        project_context = {
            'owner_type': project.owner_type.value if project.owner_type else None,
            'service_type': project.project_type,
        }

        # Step 1: RAG Retrieval
        retrieved = self.retriever.retrieve(
            query=scoring_item['description'],
            project_context=project_context,
            mode=mode,
            top_k=5 if mode == 'auto' else 3
        )

        # Step 2: Build Prompt
        if mode == 'auto':
            prompt = self.prompt_builder.build_auto_prompt(
                scoring_item=scoring_item,
                contexts=retrieved,
                owner_type=project_context['owner_type'] or 'enterprise'
            )
        else:
            prompt = self.prompt_builder.build_guided_prompt(
                scoring_item=scoring_item,
                insider_notes=insider_notes,
                contexts=retrieved,
                owner_type=project_context['owner_type'] or 'enterprise'
            )

        # Step 3: Generate with LLM
        llm = get_llm()
        config = self.prompt_builder.get_generation_config(mode)
        response = llm.generate(
            prompt=prompt,
            mode=mode,
            insider_notes=insider_notes,
            temperature=config['temperature'],
            max_tokens=config['max_tokens']
        )

        # Step 4: Build result
        result = {
            'section_title': scoring_item['name'],
            'score_weight': scoring_item['weight'],
            'content': response.content,
            'source_chunks': [r['id'] for r in retrieved],
            'linked_cases': [],  # auto-link in separate step
            'ai_rewrite_count': 1,
            'generation_timestamp': datetime.now().isoformat()
        }

        # Step 5: Log generation (async in production, sync here)
        self._log_generation(
            task_id=None,  # filled when task created
            operation_type='initial_generate',
            section_id=scoring_item.get('section_id'),
            prompt_used=prompt[:500],  # truncate for storage
            input_tokens=response.usage['input_tokens'],
            output_tokens=response.usage['output_tokens'],
            cost_usd=response.usage['cost_usd']
        )

        return result

    def _log_generation(
        self,
        task_id: Optional[int],
        operation_type: str,
        section_id: Optional[int],
        prompt_used: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ):
        log = GenerationLog(
            task_id=task_id,
            operation_type=operation_type,
            section_id=section_id,
            prompt_used=prompt_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd
        )
        self.db.add(log)
        self.db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/week3/test_tech_proposal_generator.py -v`
Expected: 2/2 PASS (with mocks)

- [ ] **Step 5: Commit**

```bash
git add app/core/week3_rag/tech_proposal_generator.py tests/week3/test_tech_proposal_generator.py
git commit -m "feat(week3): add TechProposalGenerator orchestrator with full RAG pipeline"
```

---

## Task 7: Pydantic Schemas + API Endpoints

**Files:**
- Create: `app/schemas/week3.py`
- Create: `app/api/v1/endpoints/tech_proposals.py`
- Modify: `app/main.py` (register router)
- Create: `tests/week3/test_api_tech_proposals.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/week3/test_api_tech_proposals.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestTechProposalAPI:
    def test_initiate_auto_generation(self):
        """POST /api/v1/projects/{id}/tech-proposal/initiate with auto mode."""
        response = client.post(
            "/api/v1/projects/1/tech-proposal/initiate",
            json={"generation_mode": "auto"}
        )
        assert response.status_code == 200
        data = response.json()
        assert 'task_id' in data
        assert data['status'] == 'generating'

    def test_initiate_guided_requires_insider_notes(self):
        """GUIDED mode must include specialist_input."""
        response = client.post(
            "/api/v1/projects/1/tech-proposal/initiate",
            json={"generation_mode": "guided", "specialist_input": []}
        )
        assert response.status_code in [400, 422]

    def test_get_proposal_content(self):
        """GET /api/v1/tech-proposals/{task_id}/content returns sections."""
        response = client.get("/api/v1/tech-proposals/1/content")
        assert response.status_code in [200, 404]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/week3/test_api_tech_proposals.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write schemas**

```python
# app/schemas/week3.py
"""Week 3 Pydantic schemas."""
from pydantic import BaseModel
from typing import Optional, Any

class SpecialistInputItem(BaseModel):
    type: str  # 'tag' or 'text'
    key: Optional[str] = None
    value: Optional[str] = None
    content: Optional[str] = None

class InitiateProposalRequest(BaseModel):
    generation_mode: str  # 'auto' or 'guided'
    specialist_input: Optional[list[SpecialistInputItem]] = None  # required for guided

class ScoringItem(BaseModel):
    name: str
    weight: float
    description: str
    keyword: Optional[str] = None

class ProposalSection(BaseModel):
    section_id: int
    section_title: str
    score_weight: float
    content: str
    source_chunks: list[int]
    linked_cases: list[dict]
    ai_rewrite_count: int
    generation_timestamp: str

class ScoringIndexItem(BaseModel):
    score_item_name: str
    score_weight: float
    corresponding_section_id: int
    page_number: Optional[int]
    keyword_matches: list[str]
    is_fully_responded: bool

class ProposalContentResponse(BaseModel):
    task_id: int
    project_id: int
    generation_mode: str
    status: str
    sections: list[ProposalSection]
    scoring_indexes: list[ScoringIndexItem]
```

- [ ] **Step 4: Write API endpoints**

```python
# app/api/v1/endpoints/tech_proposals.py
"""Week 3 API endpoints for tech proposal generation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import get_db
from app.schemas.week3 import (
    InitiateProposalRequest, ProposalContentResponse
)
from app.schemas.common import ResponseWrapper
from app.core.week3_rag.tech_proposal_generator import TechProposalGenerator
from app.models.project import Project
from app.models.enums import ProjectStatus, GenerationMode

router = APIRouter(prefix="/api/v1", tags=["tech-proposals"])

@router.post("/projects/{project_id}/tech-proposal/initiate")
def initiate_proposal(
    project_id: int,
    data: InitiateProposalRequest,
    db: Session = Depends(get_db)
):
    """Initiate tech proposal generation for a project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.APPROVED_BY_SPECIALIST:
        raise HTTPException(status_code=400, detail="Project must be approved before generating proposal")

    # GUIDED mode requires specialist_input
    if data.generation_mode == "guided" and not data.specialist_input:
        raise HTTPException(status_code=400, detail="GUIDED mode requires specialist_input")

    # Create tech_proposal_task record
    from app.models.tech_proposal import TechProposalTask
    input_config = {
        'generation_mode': data.generation_mode,
        'specialist_input': [i.model_dump() for i in (data.specialist_input or [])],
        'scoring_items': []  # filled from tender doc
    }
    task = TechProposalTask(
        project_id=project_id,
        generation_mode=data.generation_mode,
        input_config=input_config,
        status='generating'
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Update project status
    project.status = ProjectStatus.GENERATING_DOCUMENTS
    db.commit()

    return ResponseWrapper(data={
        'task_id': task.id,
        'status': 'generating',
        'estimated_sections': 5
    })

@router.get("/projects/{project_id}/tech-proposal/latest")
def get_latest_proposal(project_id: int, db: Session = Depends(get_db)):
    """Get latest tech proposal for a project."""
    from app.models.tech_proposal import TechProposalTask
    task = db.query(TechProposalTask).filter_by(
        project_id=project_id
    ).order_by(TechProposalTask.created_at.desc()).first()

    if not task:
        raise HTTPException(status_code=404, detail="No proposal found")

    return ResponseWrapper(data={
        'task_id': task.id,
        'project_id': task.project_id,
        'generation_mode': task.generation_mode,
        'status': task.status,
        'sections': task.generated_content or [],
        'editor_version': task.editor_version
    })

@router.get("/tech-proposals/{task_id}/content")
def get_proposal_content(task_id: int, db: Session = Depends(get_db)):
    """Get full proposal content with sections and scoring indexes."""
    from app.models.tech_proposal import TechProposalTask, ScoringIndex

    task = db.get(TechProposalTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    indexes = db.query(ScoringIndex).filter_by(project_id=task.project_id).all()

    return ResponseWrapper(data={
        'task_id': task.id,
        'project_id': task.project_id,
        'generation_mode': task.generation_mode,
        'status': task.status,
        'sections': task.generated_content or [],
        'scoring_indexes': [
            {
                'score_item_name': idx.score_item_name,
                'score_weight': float(idx.score_weight),
                'corresponding_section_id': idx.corresponding_section_id,
                'page_number': idx.page_number,
                'is_fully_responded': idx.is_fully_responded
            }
            for idx in indexes
        ]
    })

@router.post("/tech-proposals/{task_id}/sections/{section_id}/rewrite")
def rewrite_section(
    task_id: int,
    section_id: int,
    style: str = "more_professional",
    db: Session = Depends(get_db)
):
    """Rewrite a section with AI (editor's AI polish feature)."""
    from app.models.tech_proposal import TechProposalTask, GenerationLog
    task = db.get(TechProposalTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Find the section
    sections = task.generated_content or []
    section = next((s for s in sections if s['section_id'] == section_id), None)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Re-generate with style hint
    generator = TechProposalGenerator(db)
    new_content = generator.generate_section(
        project_id=task.project_id,
        scoring_item={'name': section['section_title'], 'weight': section.get('score_weight', 0), 'description': section['content'][:200]},
        mode=task.generation_mode
    )

    # Update section in-place
    for s in sections:
        if s['section_id'] == section_id:
            s['content'] = new_content['content']
            s['ai_rewrite_count'] = s.get('ai_rewrite_count', 1) + 1
            break

    task.generated_content = sections
    task.editor_version += 1
    db.commit()

    return ResponseWrapper(data={'status': 'rewritten', 'editor_version': task.editor_version})
```

- [ ] **Step 5: Register router in main.py**

In `app/main.py`, add:
```python
from app.api.v1.endpoints import tech_proposals
app.include_router(tech_proposals.router)
```

- [ ] **Step 6: Run API tests**

Run: `pytest tests/week3/test_api_tech_proposals.py -v`
Expected: 3/3 PASS

- [ ] **Step 7: Commit**

```bash
git add app/schemas/week3.py app/api/v1/endpoints/tech_proposals.py app/main.py tests/week3/test_api_tech_proposals.py
git commit -m "feat(week3): add FastAPI endpoints for tech proposal generation with TDD tests"
```

---

## Task 8: Scoring Index Generator

**Files:**
- Create: `app/core/week3_rag/scoring_index_generator.py`
- Create: `tests/week3/test_scoring_index_generator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/week3/test_scoring_index_generator.py
import pytest
from app.core.week3_rag.scoring_index_generator import ScoringIndexGenerator

class TestScoringIndexGenerator:
    def test_generates_index_per_section(self):
        """One scoring index per section is generated."""
        sections = [
            {'section_id': 1, 'section_title': '配送方案', 'score_weight': 20, 'content': 'x' * 600},
            {'section_id': 2, 'section_title': '食品安全', 'score_weight': 15, 'content': 'y' * 600},
        ]
        generator = ScoringIndexGenerator(db_session)
        indexes = generator.generate(project_id=1, sections=sections)
        assert len(indexes) == 2

    def test_page_estimation(self):
        """~600 chars = ~1 page."""
        sections = [
            {'section_id': 1, 'section_title': '测试', 'score_weight': 10, 'content': 'x' * 1200},
        ]
        indexes = generator.generate(project_id=1, sections=sections)
        assert indexes[0]['start_page'] == 3  # page 1=cover, page 2=index
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/week3/test_scoring_index_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Write ScoringIndexGenerator**

```python
# app/core/week3_rag/scoring_index_generator.py
"""Scoring Index Generator - per Week 3 spec §3.3 C-strategy scoring navigation."""
import re
from sqlalchemy.orm import Session
from app.models.tech_proposal import ScoringIndex

class ScoringIndexGenerator:
    """
    Generates scoring_indexes records for a proposal's sections.

    C-strategy: Expert-friendly navigation index.
    Each scoring item → section → page number → keywords for expert quick-locate.
    """

    CHARS_PER_PAGE = 600  # ~800 chars ≈ 1.5 pages with tables
    COVER_PAGES = 2  # cover + scoring index

    def generate(self, db: Session, project_id: int, sections: list[dict]) -> list[dict]:
        """
        Generate scoring indexes for all sections.

        Args:
            db: SQLAlchemy session
            project_id: Project ID
            sections: List of generated section dicts

        Returns:
            List of scoring index dicts
        """
        indexes = []
        current_page = self.COVER_PAGES + 1  # start after cover + index page

        for section in sections:
            content = section.get('content', '')
            estimated_pages = max(1, len(content) // self.CHARS_PER_PAGE + 1)
            keywords = self._extract_keywords(content)

            idx_record = ScoringIndex(
                project_id=project_id,
                score_item_name=section['section_title'],
                score_weight=section.get('score_weight', 0),
                corresponding_section_id=section.get('section_id'),
                corresponding_section_title=section['section_title'],
                page_number=current_page,
                keyword_matches=keywords,
                is_fully_responded=False
            )
            db.add(idx_record)

            indexes.append({
                'score_item_name': section['section_title'],
                'score_weight': section.get('score_weight', 0),
                'corresponding_section_id': section.get('section_id'),
                'start_page': current_page,
                'end_page': current_page + estimated_pages - 1,
                'keyword_matches': keywords,
                'is_fully_responded': False
            })

            current_page += estimated_pages

        db.commit()
        return indexes

    def _extract_keywords(self, text: str, top_n: int = 5) -> list[str]:
        """Extract top keywords from text (simple frequency-based)."""
        # Remove punctuation and split
        words = re.findall(r'[\u4e00-\u9fff]+', text)  # Chinese words
        # Simple: count occurrences
        freq = {}
        for word in words:
            if len(word) >= 2:
                freq[word] = freq.get(word, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/week3/test_scoring_index_generator.py -v`
Expected: 2/2 PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/week3_rag/scoring_index_generator.py tests/week3/test_scoring_index_generator.py
git commit -m "feat(week3): add ScoringIndexGenerator for expert-friendly C-strategy navigation"
```

---

## Task 9: Mode Switching (Rollback) Service

**Files:**
- Create: `app/core/week3_rag/mode_switch_service.py`
- Create: `tests/week3/test_mode_switch.py`

Per Master Spec §5.3: when `relationship_flag` changes, archived content must be marked, not deleted.

- [ ] **Step 1: Write tests and implementation**

```python
# tests/week3/test_mode_switch.py
class TestModeSwitchService:
    def test_auto_to_guided_archives_existing_proposal(self):
        """Switching AUTO→GUIDED marks existing proposal as archived."""
        ...

    def test_guided_to_auto_discards_custom_content(self):
        """GUIDED→AUTO discards guided content, starts fresh."""
        ...
```

```python
# app/core/week3_rag/mode_switch_service.py
"""Mode Switch Service - handles generation_mode transitions per Master Spec §5.3."""
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.tech_proposal import TechProposalTask
from app.models.enums import GenerationMode

class ModeSwitchService:
    """
    Handles generation_mode switches with mandatory rollback procedures.

    AUTO → GUIDED (升维):
      - Mark current proposal as 'archived_due_to_mode_switch'
      - Require specialist to re-enter insider notes
      - Start fresh generation

    GUIDED → AUTO (降维):
      - Mark current proposal as 'discarded_due_to_mode_switch'
      - Resume full AUTO RAG pipeline
    """

    def switch_mode(
        self,
        db: Session,
        project_id: int,
        new_mode: str,
        operator_id: int
    ) -> dict:
        """Switch project from current generation_mode to new_mode."""
        project = db.get(Project, project_id)
        old_mode = project.generation_mode

        if old_mode == new_mode:
            return {'status': 'unchanged', old_mode: old_mode}

        # Find and archive existing proposal
        task = db.query(TechProposalTask).filter_by(
            project_id=project_id
        ).order_by(TechProposalTask.created_at.desc()).first()

        if task:
            if old_mode == 'auto' and new_mode == 'guided':
                task.status = 'archived_due_to_mode_switch'
            elif old_mode == 'guided' and new_mode == 'auto':
                task.status = 'discarded_due_to_mode_switch'

        project.generation_mode = new_mode
        db.commit()

        return {'status': 'switched', 'old_mode': old_mode, 'new_mode': new_mode}
```

---

## Verification

- [ ] **Final: Run full Week 3 test suite**

Run: `pytest tests/week3/ -v`
Expected: All tests PASS (mocked LLM, no real API calls)

```bash
pytest tests/week3/ -v --tb=short
```

---

## Summary: Week 3 Deliverables

| Component | File | Tests |
|-----------|------|-------|
| DB Migration | `w003_add_week3_tables.py` | — |
| KnowledgeChunk Model | `app/models/knowledge_chunk.py` | — |
| TechProposal Models | `app/models/tech_proposal.py` | — |
| Text Chunker | `app/core/week3_rag/text_chunker.py` | 3 tests |
| Embedding Service | `app/core/week3_rag/embedding_service.py` | 3 tests |
| Mock LLM | `app/core/week3_rag/llm_mock.py` | 2 tests |
| Hybrid Retriever | `app/core/week3_rag/hybrid_retriever.py` | 3 tests |
| Prompt Builder | `app/core/week3_rag/prompt_builder.py` | 4 tests |
| TechProposal Generator | `app/core/week3_rag/tech_proposal_generator.py` | 2 tests |
| Scoring Index Generator | `app/core/week3_rag/scoring_index_generator.py` | 2 tests |
| Mode Switch Service | `app/core/week3_rag/mode_switch_service.py` | 2 tests |
| API Endpoints | `app/api/v1/endpoints/tech_proposals.py` | 3 tests |
| **Total** | | **~26 tests** |
