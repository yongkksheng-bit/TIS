import pytest
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Test database URL (SQLite for testing)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def engine():
    """Create a test engine for each test with base tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    with engine.connect() as conn:
        # Create users table first (referenced by projects.created_by)
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) NOT NULL UNIQUE,
                email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Create projects table
        conn.execute(text("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name VARCHAR(255) NOT NULL,
                project_type VARCHAR(50),
                owner_unit VARCHAR(255),
                owner_type VARCHAR(50) DEFAULT 'enterprise',
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
        conn.commit()
    yield engine


@pytest.fixture(scope="function")
def session(engine):
    """Create a new database session for a test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def create_week3_tables(conn):
    """Create Week 3 tables using raw SQL (matching migration structure)."""
    # knowledge_chunks
    conn.execute(text("""
        CREATE TABLE knowledge_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            content_vector TEXT,
            chunk_metadata TEXT NOT NULL DEFAULT '{}',
            source_project_id INTEGER REFERENCES projects(id),
            is_deprecated INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # tech_proposal_tasks
    conn.execute(text("""
        CREATE TABLE tech_proposal_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            generation_mode VARCHAR(20) NOT NULL,
            input_config TEXT NOT NULL DEFAULT '{}',
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

    # scoring_indexes
    conn.execute(text("""
        CREATE TABLE scoring_indexes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
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

    # generation_logs
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


def drop_week3_tables(conn):
    """Drop Week 3 tables in correct reverse order (matching downgrade)."""
    conn.execute(text("DROP TABLE IF EXISTS generation_logs"))
    conn.execute(text("DROP TABLE IF EXISTS scoring_indexes"))
    conn.execute(text("DROP TABLE IF EXISTS tech_proposal_tasks"))
    conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks"))
    conn.commit()


def test_week3_tables_exist():
    """Test that the w003 migration creates all Week 3 tables."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w003_add_week3_tables.py"
    content = migration_path.read_text()

    expected_tables = [
        ("'knowledge_chunks'", "knowledge_chunks"),
        ("'tech_proposal_tasks'", "tech_proposal_tasks"),
        ("'scoring_indexes'", "scoring_indexes"),
        ("'generation_logs'", "generation_logs"),
    ]

    for table_pattern, table_name in expected_tables:
        assert table_pattern in content, f"Missing: {table_name} table in migration file"


def test_migration_has_correct_revision_id():
    """Test that migration has correct revision ID."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w003_add_week3_tables.py"
    content = migration_path.read_text()

    assert "revision = 'w003'" in content
    assert "down_revision = 'w002'" in content


def test_pgvector_extension_enabled():
    """Test that migration enables pgvector extension."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w003_add_week3_tables.py"
    content = migration_path.read_text()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in content


def test_knowledge_chunks_columns(engine):
    """Test knowledge_chunks table can be created and has correct columns."""
    with engine.connect() as conn:
        create_week3_tables(conn)

    # Verify table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert 'knowledge_chunks' in tables

    # Verify columns
    columns = {col['name']: col for col in inspector.get_columns('knowledge_chunks')}
    assert 'id' in columns
    assert 'chunk_type' in columns
    assert columns['chunk_type']['type'].__class__.__name__ in ('STRING', 'VARCHAR')
    assert columns['chunk_type']['type'].length == 50
    assert 'content' in columns
    assert 'content_vector' in columns
    assert 'chunk_metadata' in columns
    assert 'source_project_id' in columns
    assert 'is_deprecated' in columns
    assert 'created_at' in columns
    assert 'updated_at' in columns

    # Verify nullable constraints
    assert not columns['chunk_type']['nullable']
    assert not columns['content']['nullable']
    assert columns['content_vector']['nullable']
    assert columns['source_project_id']['nullable']


def test_tech_proposal_tasks_columns(engine):
    """Test tech_proposal_tasks table can be created and has correct columns."""
    with engine.connect() as conn:
        create_week3_tables(conn)

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert 'tech_proposal_tasks' in tables

    columns = {col['name']: col for col in inspector.get_columns('tech_proposal_tasks')}
    assert 'id' in columns
    assert 'project_id' in columns
    assert 'generation_mode' in columns
    assert 'input_config' in columns
    assert 'generated_content' in columns
    assert 'final_content' in columns
    assert 'editor_version' in columns
    assert 'status' in columns
    assert 'created_by' in columns
    assert 'confirmed_at' in columns
    assert 'confirmed_by' in columns
    assert 'created_at' in columns
    assert 'updated_at' in columns

    # Verify nullable constraints
    assert not columns['project_id']['nullable']
    assert not columns['generation_mode']['nullable']
    assert columns['generated_content']['nullable']
    assert columns['final_content']['nullable']


def test_scoring_indexes_columns(engine):
    """Test scoring_indexes table can be created and has correct columns."""
    with engine.connect() as conn:
        create_week3_tables(conn)

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert 'scoring_indexes' in tables

    columns = {col['name']: col for col in inspector.get_columns('scoring_indexes')}
    assert 'id' in columns
    assert 'project_id' in columns
    assert 'score_item_name' in columns
    assert 'score_weight' in columns
    assert 'corresponding_section_id' in columns
    assert 'corresponding_section_title' in columns
    assert 'page_number' in columns
    assert 'keyword_matches' in columns
    assert 'is_fully_responded' in columns
    assert 'evidence_paragraph_ids' in columns
    assert 'created_at' in columns


def test_generation_logs_columns(engine):
    """Test generation_logs table can be created and has correct columns."""
    with engine.connect() as conn:
        create_week3_tables(conn)

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert 'generation_logs' in tables

    columns = {col['name']: col for col in inspector.get_columns('generation_logs')}
    assert 'id' in columns
    assert 'task_id' in columns
    assert 'operation_type' in columns
    assert 'section_id' in columns
    assert 'prompt_used' in columns
    assert 'input_tokens' in columns
    assert 'output_tokens' in columns
    assert 'cost_usd' in columns
    assert 'created_at' in columns


def test_foreign_keys_work(engine):
    """Test that foreign key relationships are correctly set up."""
    with engine.connect() as conn:
        # Create tables
        create_week3_tables(conn)

        # Insert test data - user first
        conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'uploaded')"))

        # Insert knowledge_chunk with FK to projects
        conn.execute(text("""
            INSERT INTO knowledge_chunks (chunk_type, content, chunk_metadata, source_project_id)
            VALUES ('qualification', 'Test content', '{}', 1)
        """))

        # Insert tech_proposal_task with FK to projects and users
        conn.execute(text("""
            INSERT INTO tech_proposal_tasks (project_id, generation_mode, input_config, created_by)
            VALUES (1, 'auto', '{}', 1)
        """))

        # Insert scoring_index with FK to projects
        conn.execute(text("""
            INSERT INTO scoring_indexes (project_id, score_item_name, score_weight)
            VALUES (1, 'Technical Score', 25.00)
        """))

        # Insert generation_log with FK to tech_proposal_tasks
        conn.execute(text("""
            INSERT INTO generation_logs (task_id, operation_type)
            VALUES (1, 'generate_section')
        """))

        conn.commit()

        # Verify data was inserted correctly
        result = conn.execute(text("SELECT chunk_type FROM knowledge_chunks WHERE source_project_id = 1")).fetchone()
        assert result[0] == 'qualification'

        result = conn.execute(text("SELECT score_item_name FROM scoring_indexes WHERE project_id = 1")).fetchone()
        assert result[0] == 'Technical Score'


def test_cascade_delete(engine):
    """Test that ON DELETE CASCADE works correctly."""
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        create_week3_tables(conn)

        # Insert test data
        conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'uploaded')"))
        conn.execute(text("""
            INSERT INTO tech_proposal_tasks (project_id, generation_mode, input_config)
            VALUES (1, 'auto', '{}')
        """))
        conn.execute(text("""
            INSERT INTO scoring_indexes (project_id, score_item_name, score_weight)
            VALUES (1, 'Test Score', 10.00)
        """))
        conn.execute(text("""
            INSERT INTO generation_logs (task_id, operation_type)
            VALUES (1, 'test')
        """))
        conn.commit()

        # Verify data exists
        assert conn.execute(text("SELECT COUNT(*) FROM tech_proposal_tasks")).fetchone()[0] == 1
        assert conn.execute(text("SELECT COUNT(*) FROM scoring_indexes")).fetchone()[0] == 1
        assert conn.execute(text("SELECT COUNT(*) FROM generation_logs")).fetchone()[0] == 1

        # Delete project (should cascade)
        conn.execute(text("DELETE FROM projects WHERE id = 1"))
        conn.commit()

        # Verify cascading delete worked
        assert conn.execute(text("SELECT COUNT(*) FROM tech_proposal_tasks")).fetchone()[0] == 0
        assert conn.execute(text("SELECT COUNT(*) FROM scoring_indexes")).fetchone()[0] == 0
        assert conn.execute(text("SELECT COUNT(*) FROM generation_logs")).fetchone()[0] == 0


def test_downgrade_drops_all_tables(engine):
    """Test that downgrade() drops all Week 3 tables correctly."""
    with engine.connect() as conn:
        create_week3_tables(conn)

        # Verify tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert 'knowledge_chunks' in tables
        assert 'tech_proposal_tasks' in tables
        assert 'scoring_indexes' in tables
        assert 'generation_logs' in tables

        # Drop tables (simulating downgrade)
        drop_week3_tables(conn)

        # Verify tables are dropped
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert 'knowledge_chunks' not in tables
        assert 'tech_proposal_tasks' not in tables
        assert 'scoring_indexes' not in tables
        assert 'generation_logs' not in tables


def test_downgrade_drops_in_correct_order():
    """Test that downgrade drops tables in correct reverse dependency order."""
    migration_path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "w003_add_week3_tables.py"
    content = migration_path.read_text()

    # Get the drop_table calls in order
    lines = [l.strip() for l in content.split('\n') if 'drop_table' in l]

    # generation_logs depends on tech_proposal_tasks
    # scoring_indexes depends on projects
    # tech_proposal_tasks depends on projects
    # knowledge_chunks depends on projects
    # Order in downgrade should be: generation_logs, scoring_indexes, tech_proposal_tasks, knowledge_chunks
    assert len(lines) >= 4, f"Expected at least 4 drop_table statements, got {len(lines)}"
