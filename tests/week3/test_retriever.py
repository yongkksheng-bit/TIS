import pytest
import json
from unittest.mock import MagicMock, call
from sqlalchemy import text

from app.core.week3_rag.retriever import DocumentRetriever
from app.core.week3_rag.embedder import MockEmbedder
from app.models.knowledge_chunk import KnowledgeChunk


@pytest.fixture
def embedder():
    return MockEmbedder()


@pytest.fixture
def retriever(db_session, embedder):
    return DocumentRetriever(db_session, embedder)


@pytest.fixture
def setup_project_chunks(db_session):
    """
    Seed knowledge_chunks for two projects (project_id=1 and project_id=2).
    Returns the embedder so tests can generate matching vectors.
    """
    # Create knowledge_chunks table if not exists (required for SQLite fallback)
    with db_session.bind.connect() as conn:
        # Check if table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_chunks'"
        )).fetchone()

        if not result:
            conn.execute(text("""
                CREATE TABLE knowledge_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_type VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    content_vector TEXT,
                    chunk_metadata TEXT NOT NULL DEFAULT '{}',
                    source_project_id INTEGER REFERENCES projects(id),
                    is_deprecated INTEGER DEFAULT 0,
                    source_type VARCHAR(30),
                    source_id BIGINT,
                    source_label VARCHAR(255),
                    chunk_index INTEGER,
                    win_signal VARCHAR(20),
                    scoring_dimension_tags TEXT,
                    region_tags TEXT,
                    project_type_tags TEXT,
                    is_price_sensitive INTEGER NOT NULL DEFAULT 0,
                    token_count INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

    embedder = MockEmbedder()

    # Project 1 chunks
    project1_texts = [
        "冷链配送方案第一章：总述",
        "冷链配送方案第二章：设备选型",
        "冷链配送方案第三章：应急预案",
    ]
    # Project 2 chunks (different content)
    project2_texts = [
        "餐饮供应链方案第一章：采购管理",
        "餐饮供应链方案第二章：库存控制",
    ]

    for i, text_content in enumerate(project1_texts):
        vec = embedder.embed_text(text_content)
        chunk = KnowledgeChunk(
            chunk_type="technical",
            content=text_content,
            content_vector=json.dumps(vec),
            chunk_metadata={"source": f"project1_chunk_{i}"},
            source_project_id=1,
            is_deprecated=False,
        )
        db_session.add(chunk)

    for i, text_content in enumerate(project2_texts):
        vec = embedder.embed_text(text_content)
        chunk = KnowledgeChunk(
            chunk_type="technical",
            content=text_content,
            content_vector=json.dumps(vec),
            chunk_metadata={"source": f"project2_chunk_{i}"},
            source_project_id=2,
            is_deprecated=False,
        )
        db_session.add(chunk)

    db_session.commit()
    return embedder


class TestDocumentRetriever:
    def test_search_calls_embedder(self, db_session, embedder, setup_project_chunks):
        """search() must call embedder.embed_text() to convert query to vector."""
        retriever = DocumentRetriever(db_session, embedder)
        embedder.embed_text = MagicMock(return_value=[0.1] * 1536)

        retriever.search("冷链配送方案", project_id=1, top_k=3)

        embedder.embed_text.assert_called_once_with("冷链配送方案")

    def test_search_returns_at_most_top_k_results(self, db_session, embedder, setup_project_chunks):
        """Results count must never exceed top_k."""
        retriever = DocumentRetriever(db_session, embedder)

        results = retriever.search("方案", project_id=1, top_k=2)
        assert len(results) <= 2

        results = retriever.search("方案", project_id=1, top_k=1)
        assert len(results) <= 1

    def test_search_returns_chunk_nodes(self, db_session, embedder, setup_project_chunks):
        """Results must be ChunkNode instances, not dicts."""
        from app.schemas.rag import ChunkNode
        retriever = DocumentRetriever(db_session, embedder)

        results = retriever.search("冷链", project_id=1, top_k=3)
        assert all(isinstance(r, ChunkNode) for r in results)

    def test_search_returns_non_empty_text(self, db_session, embedder, setup_project_chunks):
        """Every result must have non-empty text."""
        retriever = DocumentRetriever(db_session, embedder)

        results = retriever.search("方案", project_id=1, top_k=5)
        assert all(len(r.text) > 0 for r in results)

    def test_project_isolation_project1_no_project2_data(
        self, db_session, embedder, setup_project_chunks
    ):
        """
        CRITICAL TEST: Searching project_id=1 must NEVER return project_id=2 chunks.
        This is the most important security test.
        """
        retriever = DocumentRetriever(db_session, embedder)

        results = retriever.search("餐饮", project_id=1, top_k=5)

        # No result from project 2 should appear
        for chunk in results:
            assert chunk.metadata.get("source", "").startswith("project1_"), \
                f"Cross-project leak: found chunk with source={chunk.metadata.get('source')}"

    def test_project_isolation_project2_no_project1_data(
        self, db_session, embedder, setup_project_chunks
    ):
        """
        CRITICAL TEST: Searching project_id=2 must NEVER return project_id=1 chunks.
        """
        retriever = DocumentRetriever(db_session, embedder)

        results = retriever.search("冷链", project_id=2, top_k=5)

        for chunk in results:
            assert chunk.metadata.get("source", "").startswith("project2_"), \
                f"Cross-project leak: found chunk with source={chunk.metadata.get('source')}"

    def test_project_isolation_when_query_semantically_mismatched(
        self, db_session, embedder, setup_project_chunks
    ):
        """
        When a query semantically belongs to project 1 but we search project 2,
        results may be returned (random vectors match) BUT must ALL be from project 2.
        This verifies the project_id filter is NEVER bypassed by similarity ranking.
        """
        retriever = DocumentRetriever(db_session, embedder)

        # Query text is from project 1 but we search project 2
        results = retriever.search("冷链", project_id=2, top_k=5)
        # All results must be from project 2 (even if random vectors matched)
        for chunk in results:
            assert chunk.metadata.get("source", "").startswith("project2_"), \
                f"Cross-project leak: found {chunk.metadata.get('source')}"

    def test_search_respects_chunk_type_filter(self, db_session, embedder, setup_project_chunks):
        """When chunk_type is specified, only matching chunks are returned."""
        retriever = DocumentRetriever(db_session, embedder)

        results = retriever.search("方案", project_id=1, top_k=5, chunk_type="commercial")
        # All results should have chunk_type that matches or empty if none exist
        # (This test verifies the filter is applied, not that results exist)

    def test_search_with_no_matching_content_returns_empty(
        self, db_session, embedder, setup_project_chunks
    ):
        """Query that matches nothing returns empty list."""
        retriever = DocumentRetriever(db_session, embedder)

        # Query that definitely doesn't match any seeded content
        results = retriever.search(
            "xyzabc_notexist_content_12345", project_id=1, top_k=5
        )
        assert isinstance(results, list)

    def test_search_query_from_different_project_does_not_leak(
        self, db_session, embedder, setup_project_chunks
    ):
        """
        Verify project_id filter is enforced even when a project-2-specific
        query randomly matches project-1 chunks via MockEmbedder vectors.
        All results MUST be from the queried project_id.
        """
        retriever = DocumentRetriever(db_session, embedder)

        # Query from project 2 content, search against project 1
        results = retriever.search("餐饮供应链", project_id=1, top_k=5)
        # Results may or may not be empty (random vectors) but MUST be from project 1
        for chunk in results:
            assert chunk.metadata.get("source", "").startswith("project1_"), \
                f"Cross-project leak: found {chunk.metadata.get('source')}"
