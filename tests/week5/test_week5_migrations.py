"""TDD tests for Week 5 formal review table migrations."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_engine():
    """In-memory SQLite engine for migration testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
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
        conn.execute(text("""
            CREATE TABLE cost_estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                version_number INTEGER NOT NULL DEFAULT 1,
                food_cost NUMERIC(15, 2) NOT NULL,
                logistics_cost NUMERIC(15, 2) NOT NULL,
                labor_cost NUMERIC(15, 2) NOT NULL,
                management_cost NUMERIC(15, 2) NOT NULL,
                other_cost NUMERIC(15, 2) NOT NULL DEFAULT 0,
                total_cost NUMERIC(15, 2) NOT NULL,
                estimated_by INTEGER REFERENCES users(id),
                estimate_reason TEXT,
                is_confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE pricing_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                cost_estimate_id INTEGER REFERENCES cost_estimates(id),
                cost_base NUMERIC(15, 2) NOT NULL,
                system_suggested_low NUMERIC(15, 2) NOT NULL,
                system_suggested_high NUMERIC(15, 2) NOT NULL,
                system_suggested_optimal NUMERIC(15, 2),
                finance_suggested_price NUMERIC(15, 2),
                finance_suggestion_reason TEXT,
                boss_final_price NUMERIC(15, 2) NOT NULL,
                boss_decision_reason TEXT,
                deviation_from_system NUMERIC(5, 4),
                deviation_reason_category VARCHAR(50),
                budget_limit NUMERIC(15, 2),
                is_under_limit INTEGER,
                limit_violation_warning TEXT,
                game_theory_analysis TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'decided',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
    return engine


class TestFormalReviewItemsTable:
    def test_table_exists(self, db_engine):
        """formal_review_items table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE formal_review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    source_type VARCHAR(50) NOT NULL,
                    parent_item_id INTEGER REFERENCES formal_review_items(id),
                    check_category VARCHAR(50) NOT NULL,
                    check_title VARCHAR(255) NOT NULL,
                    check_description TEXT,
                    reference_clause TEXT,
                    system_status VARCHAR(20) NOT NULL,
                    system_evidence TEXT,
                    specialist_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    specialist_notes TEXT,
                    corrected_evidence TEXT,
                    confirmed_by INTEGER REFERENCES users(id),
                    confirmed_at TIMESTAMP,
                    pdf_highlight_coords TEXT,
                    risk_level VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='formal_review_items'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """All formal_review_items columns are present."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE formal_review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    parent_item_id INTEGER,
                    check_category VARCHAR(50) NOT NULL,
                    check_title VARCHAR(255) NOT NULL,
                    check_description TEXT,
                    reference_clause TEXT,
                    system_status VARCHAR(20) NOT NULL,
                    system_evidence TEXT,
                    specialist_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    specialist_notes TEXT,
                    corrected_evidence TEXT,
                    confirmed_by INTEGER,
                    confirmed_at TIMESTAMP,
                    pdf_highlight_coords TEXT,
                    risk_level VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()
            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(formal_review_items)"))}
        required_cols = {
            'id', 'project_id', 'source_type', 'parent_item_id', 'check_category',
            'check_title', 'check_description', 'reference_clause', 'system_status',
            'system_evidence', 'specialist_status', 'specialist_notes', 'corrected_evidence',
            'confirmed_by', 'confirmed_at', 'pdf_highlight_coords', 'risk_level',
            'created_at', 'updated_at'
        }
        assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

    def test_project_fk_cascade(self, db_engine):
        """project_id FK has ON DELETE CASCADE."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE formal_review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    source_type VARCHAR(50) NOT NULL,
                    parent_item_id INTEGER REFERENCES formal_review_items(id) ON DELETE CASCADE,
                    check_category VARCHAR(50) NOT NULL,
                    check_title VARCHAR(255) NOT NULL,
                    check_description TEXT,
                    reference_clause TEXT,
                    system_status VARCHAR(20) NOT NULL,
                    system_evidence TEXT,
                    specialist_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    specialist_notes TEXT,
                    corrected_evidence TEXT,
                    confirmed_by INTEGER REFERENCES users(id),
                    confirmed_at TIMESTAMP,
                    pdf_highlight_coords TEXT,
                    risk_level VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()
            fks = conn.execute(text("PRAGMA foreign_key_list(formal_review_items)")).fetchall()
        # fk tuple: (seq, id, table, from_col, to_col, on_update, on_delete, match)
        assert any(fk[2] == 'projects' and fk[6] == 'CASCADE' for fk in fks)

    def test_source_type_check(self, db_engine):
        """source_type CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE formal_review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    parent_item_id INTEGER,
                    check_category VARCHAR(50) NOT NULL,
                    check_title VARCHAR(255) NOT NULL,
                    check_description TEXT,
                    reference_clause TEXT,
                    system_status VARCHAR(20) NOT NULL,
                    system_evidence TEXT,
                    specialist_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    specialist_notes TEXT,
                    corrected_evidence TEXT,
                    confirmed_by INTEGER,
                    confirmed_at TIMESTAMP,
                    pdf_highlight_coords TEXT,
                    risk_level VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    CHECK (source_type IN ('system_parsed','ocr_comparison','content_integrity','manual_added'))
                )
            """))
            conn.commit()
            # Valid insert should succeed
            conn.execute(text(
                "INSERT INTO formal_review_items (project_id, source_type, check_category, check_title, system_status, risk_level) "
                "VALUES (1, 'system_parsed', 'qualification_validity', 'Test', 'passed', 'info')"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT source_type FROM formal_review_items WHERE id=1"
            )).fetchone()
        assert result[0] == 'system_parsed'

    def test_risk_level_check(self, db_engine):
        """risk_level CHECK constraint accepts fatal/warning/info."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE formal_review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    source_type VARCHAR(50) NOT NULL,
                    parent_item_id INTEGER,
                    check_category VARCHAR(50) NOT NULL,
                    check_title VARCHAR(255) NOT NULL,
                    check_description TEXT,
                    reference_clause TEXT,
                    system_status VARCHAR(20) NOT NULL,
                    system_evidence TEXT,
                    specialist_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    specialist_notes TEXT,
                    corrected_evidence TEXT,
                    confirmed_by INTEGER,
                    confirmed_at TIMESTAMP,
                    pdf_highlight_coords TEXT,
                    risk_level VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    CHECK (risk_level IN ('fatal','warning','info'))
                )
            """))
            conn.commit()
            # Valid insert should succeed
            conn.execute(text(
                "INSERT INTO formal_review_items (project_id, source_type, check_category, check_title, system_status, risk_level) "
                "VALUES (1, 'system_parsed', 'qualification_validity', 'Test', 'failed', 'fatal')"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT risk_level FROM formal_review_items WHERE id=1"
            )).fetchone()
        assert result[0] == 'fatal'


class TestAbandonedDraftsTable:
    def test_table_exists(self, db_engine):
        """abandoned_drafts table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE abandoned_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    termination_stage VARCHAR(50),
                    tech_proposal_path VARCHAR(500),
                    business_proposal_path VARCHAR(500),
                    pricing_decision_id INTEGER REFERENCES pricing_decisions(id),
                    termination_reason TEXT,
                    termination_by INTEGER REFERENCES users(id),
                    can_be_revived INTEGER NOT NULL DEFAULT 1,
                    archived_at TIMESTAMP,
                    revived_at TIMESTAMP,
                    revived_to_project_id INTEGER REFERENCES projects(id)
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='abandoned_drafts'"
            )).fetchone()
        assert result is not None

    def test_termination_stage_check(self, db_engine):
        """termination_stage CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE abandoned_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    termination_stage VARCHAR(50),
                    tech_proposal_path VARCHAR(500),
                    business_proposal_path VARCHAR(500),
                    pricing_decision_id INTEGER,
                    termination_reason TEXT,
                    termination_by INTEGER,
                    can_be_revived INTEGER NOT NULL DEFAULT 1,
                    archived_at TIMESTAMP,
                    revived_at TIMESTAMP,
                    revived_to_project_id INTEGER,
                    CHECK (termination_stage IN ('formal_review','pricing','tech_generation') OR termination_stage IS NULL)
                )
            """))
            conn.commit()
            # Valid insert should succeed
            conn.execute(text(
                "INSERT INTO abandoned_drafts (project_id, termination_stage, can_be_revived) "
                "VALUES (1, 'formal_review', 1)"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT termination_stage FROM abandoned_drafts WHERE id=1"
            )).fetchone()
        assert result[0] == 'formal_review'


class TestFinalBidDocumentsTable:
    def test_table_exists(self, db_engine):
        """final_bid_documents table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE final_bid_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    document_type VARCHAR(50),
                    file_path VARCHAR(500),
                    file_size INTEGER,
                    generated_by INTEGER REFERENCES users(id),
                    generated_at TIMESTAMP,
                    generation_status VARCHAR(20) NOT NULL DEFAULT 'generating',
                    error_log TEXT,
                    packaging_guide TEXT
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='final_bid_documents'"
            )).fetchone()
        assert result is not None

    def test_generation_status_check(self, db_engine):
        """generation_status CHECK constraint accepts generating/completed/failed."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE final_bid_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    document_type VARCHAR(50),
                    file_path VARCHAR(500),
                    file_size INTEGER,
                    generated_by INTEGER,
                    generated_at TIMESTAMP,
                    generation_status VARCHAR(20) NOT NULL DEFAULT 'generating',
                    error_log TEXT,
                    packaging_guide TEXT,
                    CHECK (generation_status IN ('generating','completed','failed'))
                )
            """))
            conn.commit()
            # Valid insert should succeed
            conn.execute(text(
                "INSERT INTO final_bid_documents (project_id, generation_status) "
                "VALUES (1, 'generating')"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT generation_status FROM final_bid_documents WHERE id=1"
            )).fetchone()
        assert result[0] == 'generating'


class TestCascadeDelete:
    def test_cascade_delete_project_removes_formal_review_items(self, db_engine):
        """ON DELETE CASCADE removes formal_review_items when project deleted."""
        with db_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("""
                CREATE TABLE formal_review_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    source_type VARCHAR(50) NOT NULL,
                    parent_item_id INTEGER,
                    check_category VARCHAR(50) NOT NULL,
                    check_title VARCHAR(255) NOT NULL,
                    check_description TEXT,
                    reference_clause TEXT,
                    system_status VARCHAR(20) NOT NULL,
                    system_evidence TEXT,
                    specialist_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    specialist_notes TEXT,
                    corrected_evidence TEXT,
                    confirmed_by INTEGER,
                    confirmed_at TIMESTAMP,
                    pdf_highlight_coords TEXT,
                    risk_level VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            conn.commit()
            conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test', 'uploaded')"))
            conn.execute(text(
                "INSERT INTO formal_review_items (project_id, source_type, check_category, check_title, system_status, risk_level) "
                "VALUES (1, 'system_parsed', 'qualification_validity', 'Test', 'passed', 'info')"
            ))
            conn.commit()
            conn.execute(text("DELETE FROM projects WHERE id=1"))
            conn.commit()
            result = conn.execute(text(
                "SELECT COUNT(*) FROM formal_review_items WHERE project_id=1"
            )).fetchone()
        assert result[0] == 0
