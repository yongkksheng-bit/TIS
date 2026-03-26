import pytest
import re
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.week3_rag.scoring_index_generator import ScoringIndexGenerator
from app.models.tech_proposal import ScoringIndex, TechProposalTask


@pytest.fixture
def db_session():
    """In-memory SQLite DB with StaticPool for FK enforcement."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        # Create required tables
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) NOT NULL UNIQUE
            )
        """))
        conn.execute(text("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name VARCHAR(255) NOT NULL,
                project_type VARCHAR(50),
                owner_unit VARCHAR(255),
                region VARCHAR(100),
                budget_amount NUMERIC(15, 2),
                bid_open_date TIMESTAMP,
                status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
                relationship_flag INTEGER NOT NULL DEFAULT 0,
                generation_mode VARCHAR(20),
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE scoring_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                score_item_name VARCHAR(255) NOT NULL,
                score_weight NUMERIC(5, 2) NOT NULL,
                corresponding_section_id INTEGER,
                corresponding_section_title VARCHAR(255),
                page_number INTEGER,
                keyword_matches TEXT,
                is_fully_responded INTEGER DEFAULT 0,
                evidence_paragraph_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE tech_proposal_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                generation_mode VARCHAR(20) NOT NULL,
                input_config TEXT,
                generated_content TEXT,
                final_content TEXT,
                editor_version INTEGER DEFAULT 1,
                status VARCHAR(20) DEFAULT 'generating',
                created_by INTEGER REFERENCES users(id),
                confirmed_at TIMESTAMP,
                confirmed_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        conn.execute(text("""
            INSERT INTO projects (id, project_name, project_type, bid_open_date, status, owner_unit, region, created_by)
            VALUES (1, '测试项目', 'food', CURRENT_TIMESTAMP, 'approved_by_specialist', '某市政府', '北京', 1)
        """))
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestScoringIndexGenerator:
    def test_generates_index_per_section(self, db_session):
        """One scoring index per section is generated."""
        sections = [
            {'section_id': 1, 'section_title': '配送方案', 'score_weight': 20, 'content': 'x' * 600},
            {'section_id': 2, 'section_title': '食品安全', 'score_weight': 15, 'content': 'y' * 600},
        ]
        generator = ScoringIndexGenerator()
        indexes = generator.generate(db=db_session, project_id=1, sections=sections)
        assert len(indexes) == 2

    def test_page_estimation(self, db_session):
        """~600 chars = ~1 page, pages start after cover (2 pages)."""
        sections = [
            {'section_id': 1, 'section_title': '测试', 'score_weight': 10, 'content': 'x' * 1200},
        ]
        generator = ScoringIndexGenerator()
        indexes = generator.generate(db=db_session, project_id=1, sections=sections)
        # cover(2) + content pages
        assert indexes[0]['start_page'] == 3  # page 1=cover, page 2=index, content starts page 3

    def test_keyword_extraction(self, db_session):
        """Keywords are extracted from Chinese text."""
        sections = [
            {'section_id': 1, 'section_title': '测试', 'score_weight': 10,
             'content': '冷链配送 冷链配送 食品安全 食品 安全 标准'},
        ]
        generator = ScoringIndexGenerator()
        indexes = generator.generate(db=db_session, project_id=1, sections=sections)
        # '冷链配送' appears twice, should be top keyword
        assert 'keyword_matches' in indexes[0]
        assert isinstance(indexes[0]['keyword_matches'], list)

    def test_stores_to_database(self, db_session):
        """ScoringIndex records are actually persisted to DB."""
        sections = [
            {'section_id': 1, 'section_title': '配送方案', 'score_weight': 20, 'content': 'x' * 300},
        ]
        generator = ScoringIndexGenerator()
        generator.generate(db=db_session, project_id=1, sections=sections)

        records = db_session.query(ScoringIndex).filter_by(project_id=1).all()
        assert len(records) == 1
        assert records[0].score_item_name == '配送方案'
        assert records[0].page_number == 3

    def test_cover_pages_constant(self, db_session):
        """COVER_PAGES = 2 means content starts at page 3 regardless of content length."""
        sections = [
            {'section_id': 1, 'section_title': '第一章', 'score_weight': 10, 'content': 'short'},
        ]
        generator = ScoringIndexGenerator()
        indexes = generator.generate(db=db_session, project_id=1, sections=sections)
        assert indexes[0]['start_page'] == 3

    def test_multiple_sections_sequential_pages(self, db_session):
        """Multiple sections get sequential page numbers."""
        sections = [
            {'section_id': 1, 'section_title': '第一章', 'score_weight': 10, 'content': 'x' * 1200},  # ~2 pages
            {'section_id': 2, 'section_title': '第二章', 'score_weight': 10, 'content': 'y' * 600},  # ~1 page
        ]
        generator = ScoringIndexGenerator()
        indexes = generator.generate(db=db_session, project_id=1, sections=sections)
        # Chapter 1: page 3-4, Chapter 2: page 5
        assert indexes[0]['start_page'] == 3
        assert indexes[1]['start_page'] == 5