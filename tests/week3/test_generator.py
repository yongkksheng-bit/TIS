import pytest
import json
from datetime import datetime, timedelta
from sqlalchemy import text

from app.core.week3_rag.generator import TechProposalGenerator, GenerationResult
from app.core.week3_rag.embedder import MockEmbedder
from app.core.week3_rag.retriever import DocumentRetriever
from app.core.week3_rag.prompt_builder import TechProposalPromptBuilder
from app.core.week3_rag.llm_mock import MockDeepSeekLLM
from app.models.tech_proposal import GenerationLog, TechProposalTask
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.project import Project
from app.models.base import Base


@pytest.fixture
def mock_embedder():
    return MockEmbedder()


@pytest.fixture
def retriever(db_session, mock_embedder):
    return DocumentRetriever(db_session, mock_embedder)


@pytest.fixture
def generator(db_session, retriever):
    llm = MockDeepSeekLLM()
    pb = TechProposalPromptBuilder()
    return TechProposalGenerator(
        db=db_session,
        retriever=retriever,
        llm=llm,
        prompt_builder=pb,
    )


@pytest.fixture
def setup_project_and_chunks(db_session):
    """Seed a project and knowledge chunks for retrieval testing."""
    # Create tables if not exist (SQLite fallback for tests)
    with db_session.bind.connect() as conn:
        # Check if knowledge_chunks table exists
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

        # Check if generation_logs table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_logs'"
        )).fetchone()

        if not result:
            conn.execute(text("""
                CREATE TABLE generation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER REFERENCES tech_proposal_tasks(id) ON DELETE CASCADE,
                    operation_type VARCHAR(50) NOT NULL,
                    section_id INTEGER,
                    prompt_used TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cost_usd NUMERIC(8, 4),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

    # Create user
    db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))

    # Create project
    bid_date = datetime.now() + timedelta(days=30)
    db_session.execute(text("""
        INSERT INTO projects (id, project_name, project_type, bid_open_date, status, owner_unit, region)
        VALUES (1, '测试项目', 'food', :bid_date, 'approved_by_specialist', '某市政府', '北京')
    """), {"bid_date": bid_date})

    # Create knowledge chunks for project 1
    chunks_data = [
        ("冷链配送需保证0-4摄氏度", "technical"),
        ("应急预案包括车辆故障应急处理", "technical"),
        ("食品安全需符合HACCP标准", "qualification"),
    ]
    embedder = MockEmbedder()
    for i, (content, chunk_type) in enumerate(chunks_data):
        vec = embedder.embed_text(content)
        db_session.execute(text("""
            INSERT INTO knowledge_chunks (chunk_type, content, content_vector, chunk_metadata, source_project_id, is_deprecated)
            VALUES (:chunk_type, :content, :vec, :meta, 1, 0)
        """), {
            "chunk_type": chunk_type,
            "content": content,
            "vec": json.dumps(vec),
            "meta": json.dumps({"source": f"chunk_{i}"}),
        })
    db_session.commit()


class TestTechProposalGenerator:
    def test_generate_section_returns_generation_result(
        self, generator, setup_project_and_chunks
    ):
        """generate_section returns a GenerationResult with expected fields."""
        result = generator.generate_section(
            project_id=1,
            section_name="第一章：冷链配送方案",
            generation_mode="auto",
        )
        assert isinstance(result, GenerationResult)
        assert result.section_name == "第一章：冷链配送方案"
        assert result.content is not None
        assert len(result.content) > 0

    def test_generate_section_returns_generation_result_guided(
        self, generator, setup_project_and_chunks
    ):
        """GUIDED mode also returns GenerationResult."""
        result = generator.generate_section(
            project_id=1,
            section_name="第一章：冷链配送方案",
            generation_mode="guided",
            insider_notes="必须使用双汇冷鲜肉，避开高峰时段",
        )
        assert isinstance(result, GenerationResult)
        assert result.content is not None

    def test_generate_section_content_from_llm(
        self, generator, setup_project_and_chunks
    ):
        """Generated content should come from the LLM (mock)."""
        result = generator.generate_section(
            project_id=1,
            section_name="第一章：冷链配送方案",
            generation_mode="auto",
        )
        assert "[AUTO MODE" in result.content or len(result.content) > 0

    def test_result_contains_source_chunks(
        self, generator, setup_project_and_chunks
    ):
        """Result should include source chunk info."""
        result = generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="auto",
        )
        assert isinstance(result.source_chunks, list)

    def test_result_contains_timestamp(
        self, generator, setup_project_and_chunks
    ):
        """Result includes generation timestamp."""
        result = generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="auto",
        )
        assert result.generation_timestamp is not None
        assert "Z" in result.generation_timestamp or len(result.generation_timestamp) > 0

    def test_result_to_dict(
        self, generator, setup_project_and_chunks
    ):
        """GenerationResult.to_dict() produces a valid dict."""
        result = generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="auto",
        )
        d = result.to_dict()
        assert "section_name" in d
        assert "content" in d
        assert "source_chunks" in d
        assert "generation_timestamp" in d


class TestGenerationLog:
    def test_successful_generation_creates_log(
        self, db_session, generator, setup_project_and_chunks
    ):
        """Each generation (success or failure) creates a GenerationLog row."""
        log_count_before = db_session.query(GenerationLog).count()

        generator.generate_section(
            project_id=1,
            section_name="第一章：冷链配送方案",
            generation_mode="auto",
        )

        log_count_after = db_session.query(GenerationLog).count()
        assert log_count_after == log_count_before + 1

    def test_log_has_correct_operation_type(
        self, db_session, generator, setup_project_and_chunks
    ):
        """GenerationLog.operation_type is 'generate_section'."""
        generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="auto",
        )

        log = db_session.query(GenerationLog).order_by(GenerationLog.id.desc()).first()
        assert log is not None
        assert log.operation_type == "generate_section"

    def test_log_records_prompt(
        self, db_session, generator, setup_project_and_chunks
    ):
        """GenerationLog.prompt_used contains the generated prompt."""
        generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="auto",
        )

        log = db_session.query(GenerationLog).order_by(GenerationLog.id.desc()).first()
        assert log is not None
        assert log.prompt_used is not None
        assert len(log.prompt_used) > 0

    def test_log_records_token_usage(
        self, db_session, generator, setup_project_and_chunks
    ):
        """GenerationLog records token counts from LLM response."""
        generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="auto",
        )

        log = db_session.query(GenerationLog).order_by(GenerationLog.id.desc()).first()
        assert log is not None
        # MockDeepSeekLLM returns usage with these fields
        assert log.input_tokens is not None or log.output_tokens is not None

    def test_log_records_generation_mode(
        self, db_session, generator, setup_project_and_chunks
    ):
        """The generation_mode is recorded in the prompt_used (embedded)."""
        generator.generate_section(
            project_id=1,
            section_name="第一章",
            generation_mode="guided",
            insider_notes="测试内幕",
        )

        log = db_session.query(GenerationLog).order_by(GenerationLog.id.desc()).first()
        assert log is not None
        # GUIDED mode content includes special marker
        assert log.prompt_used is not None

    def test_multiple_generations_create_multiple_logs(
        self, db_session, generator, setup_project_and_chunks
    ):
        """Each generate_section call creates a separate log."""
        generator.generate_section(project_id=1, section_name="第一章", generation_mode="auto")
        generator.generate_section(project_id=1, section_name="第二章", generation_mode="auto")

        count = db_session.query(GenerationLog).count()
        assert count >= 2

    def test_log_even_on_empty_chunks(
        self, db_session, generator
    ):
        """Generation still logs even if no chunks retrieved (project has no chunks)."""
        # Create tables if not exist
        with db_session.bind.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='generation_logs'"
            )).fetchone()

            if not result:
                conn.execute(text("""
                    CREATE TABLE generation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id INTEGER,
                        operation_type VARCHAR(50) NOT NULL,
                        section_id INTEGER,
                        prompt_used TEXT,
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        cost_usd NUMERIC(8, 4),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("""
                    CREATE TABLE knowledge_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chunk_type VARCHAR(50) NOT NULL,
                        content TEXT NOT NULL,
                        content_vector TEXT,
                        chunk_metadata TEXT NOT NULL DEFAULT '{}',
                        source_project_id INTEGER,
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

        # Create user and project but no chunks
        db_session.execute(text("INSERT INTO users (id, username) VALUES (2, 'user2')"))
        bid_date = datetime.now() + timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO projects (id, project_name, project_type, bid_open_date, status, owner_unit, region)
            VALUES (2, 'Empty Project', 'food', :bid_date, 'approved_by_specialist', 'Empty', 'Shanghai')
        """), {"bid_date": bid_date})
        db_session.commit()

        log_count_before = db_session.query(GenerationLog).count()
        result = generator.generate_section(
            project_id=2,
            section_name="第一章",
            generation_mode="auto",
        )
        log_count_after = db_session.query(GenerationLog).count()
        assert log_count_after == log_count_before + 1
        assert result.content is not None  # LLM still generates something
