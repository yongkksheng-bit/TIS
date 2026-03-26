"""TDD tests for Week 6 review tables migrations."""
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
            CREATE TABLE knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_type VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                content_vector TEXT,
                chunk_metadata TEXT NOT NULL DEFAULT '{}',
                source_project_id INTEGER REFERENCES projects(id),
                is_deprecated INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
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
        conn.execute(text("""
            CREATE TABLE abandoned_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                termination_stage VARCHAR(50),
                tech_proposal_path VARCHAR(500),
                business_proposal_path VARCHAR(500),
                pricing_decision_id INTEGER,
                termination_reason TEXT,
                termination_by INTEGER REFERENCES users(id),
                can_be_revived INTEGER NOT NULL DEFAULT 1,
                archived_at TIMESTAMP,
                revived_at TIMESTAMP,
                revived_to_project_id INTEGER REFERENCES projects(id)
            )
        """))
        conn.commit()
    return engine


class TestBidOutcomesTable:
    def test_table_exists(self, db_engine):
        """bid_outcomes table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE bid_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    outcome_status VARCHAR(20) NOT NULL,
                    outcome_date DATE NOT NULL,
                    final_bid_price NUMERIC(15, 2) NOT NULL,
                    winning_price NUMERIC(15, 2),
                    winning_unit VARCHAR(255),
                    our_price_rank INTEGER,
                    disqualification_reason TEXT,
                    disqualification_type VARCHAR(50),
                    related_review_item_id INTEGER REFERENCES formal_review_items(id) ON DELETE SET NULL,
                    is_manual_error INTEGER NOT NULL DEFAULT 0,
                    review_analysis TEXT,
                    reviewed_by INTEGER REFERENCES users(id),
                    reviewed_at TIMESTAMP,
                    review_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (outcome_status IN ('win','lose','disqualified','abandoned','withdrawn')),
                    CHECK (disqualification_type IN ('fatal_formal','fatal_qualification','fatal_price','tech_deficiency','price_uncompetitive') OR disqualification_type IS NULL)
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bid_outcomes'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """All bid_outcomes columns are present."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE bid_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    outcome_status VARCHAR(20) NOT NULL,
                    outcome_date DATE NOT NULL,
                    final_bid_price NUMERIC(15, 2) NOT NULL,
                    winning_price NUMERIC(15, 2),
                    winning_unit VARCHAR(255),
                    our_price_rank INTEGER,
                    disqualification_reason TEXT,
                    disqualification_type VARCHAR(50),
                    related_review_item_id INTEGER,
                    is_manual_error INTEGER NOT NULL DEFAULT 0,
                    review_analysis TEXT,
                    reviewed_by INTEGER,
                    reviewed_at TIMESTAMP,
                    review_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(bid_outcomes)"))}
        required_cols = {
            'id', 'project_id', 'outcome_status', 'outcome_date', 'final_bid_price',
            'winning_price', 'winning_unit', 'our_price_rank', 'disqualification_reason',
            'disqualification_type', 'related_review_item_id', 'is_manual_error',
            'review_analysis', 'reviewed_by', 'reviewed_at', 'review_notes', 'created_at'
        }
        assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

    def test_project_fk_cascade(self, db_engine):
        """project_id FK has ON DELETE CASCADE."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE bid_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    outcome_status VARCHAR(20) NOT NULL,
                    outcome_date DATE NOT NULL,
                    final_bid_price NUMERIC(15, 2) NOT NULL,
                    is_manual_error INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (outcome_status IN ('win','lose','disqualified','abandoned','withdrawn'))
                )
            """))
            conn.commit()
            fks = conn.execute(text("PRAGMA foreign_key_list(bid_outcomes)")).fetchall()
        assert any(fk[2] == 'projects' and fk[6] == 'CASCADE' for fk in fks)

    def test_outcome_status_check(self, db_engine):
        """outcome_status CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE bid_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    outcome_status VARCHAR(20) NOT NULL,
                    outcome_date DATE NOT NULL,
                    final_bid_price NUMERIC(15, 2) NOT NULL,
                    is_manual_error INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (outcome_status IN ('win','lose','disqualified','abandoned','withdrawn'))
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO bid_outcomes (project_id, outcome_status, outcome_date, final_bid_price) "
                "VALUES (1, 'win', '2026-01-01', 100000.00)"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT outcome_status FROM bid_outcomes WHERE id=1"
            )).fetchone()
        assert result[0] == 'win'

    def test_disqualification_type_check(self, db_engine):
        """disqualification_type CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE bid_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    outcome_status VARCHAR(20) NOT NULL,
                    outcome_date DATE NOT NULL,
                    final_bid_price NUMERIC(15, 2) NOT NULL,
                    disqualification_type VARCHAR(50),
                    is_manual_error INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (disqualification_type IN ('fatal_formal','fatal_qualification','fatal_price','tech_deficiency','price_uncompetitive') OR disqualification_type IS NULL)
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO bid_outcomes (project_id, outcome_status, outcome_date, final_bid_price, disqualification_type) "
                "VALUES (1, 'disqualified', '2026-01-01', 100000.00, 'fatal_formal')"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT disqualification_type FROM bid_outcomes WHERE id=1"
            )).fetchone()
        assert result[0] == 'fatal_formal'


class TestWinningDNATable:
    def test_table_exists(self, db_engine):
        """winning_dna table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE winning_dna (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    source_chunk_id INTEGER REFERENCES knowledge_chunks(id) ON DELETE SET NULL,
                    dna_type VARCHAR(50) NOT NULL,
                    score_contribution INTEGER NOT NULL,
                    scoring_item_matched VARCHAR(255),
                    owner_type VARCHAR(50),
                    project_scale VARCHAR(50),
                    reused_in_projects TEXT DEFAULT '[]',
                    reuse_success_rate NUMERIC(5, 2),
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmed_by INTEGER REFERENCES users(id),
                    CHECK (dna_type IN ('high_score_response','winning_price_strategy','effective_case_usage','format_excellence')),
                    CHECK (score_contribution BETWEEN 1 AND 10)
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='winning_dna'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """All winning_dna columns are present."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE winning_dna (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    source_chunk_id INTEGER,
                    dna_type VARCHAR(50) NOT NULL,
                    score_contribution INTEGER NOT NULL,
                    scoring_item_matched VARCHAR(255),
                    owner_type VARCHAR(50),
                    project_scale VARCHAR(50),
                    reused_in_projects TEXT DEFAULT '[]',
                    reuse_success_rate NUMERIC(5, 2),
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmed_by INTEGER
                )
            """))
            conn.commit()
            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(winning_dna)"))}
        required_cols = {
            'id', 'project_id', 'source_chunk_id', 'dna_type', 'score_contribution',
            'scoring_item_matched', 'owner_type', 'project_scale', 'reused_in_projects',
            'reuse_success_rate', 'extracted_at', 'confirmed_by'
        }
        assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

    def test_dna_type_check(self, db_engine):
        """dna_type CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE winning_dna (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    dna_type VARCHAR(50) NOT NULL,
                    score_contribution INTEGER NOT NULL,
                    CHECK (dna_type IN ('high_score_response','winning_price_strategy','effective_case_usage','format_excellence'))
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO winning_dna (project_id, dna_type, score_contribution) "
                "VALUES (1, 'winning_price_strategy', 8)"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT dna_type FROM winning_dna WHERE id=1"
            )).fetchone()
        assert result[0] == 'winning_price_strategy'


class TestDisqualificationTrapsTable:
    def test_table_exists(self, db_engine):
        """disqualification_traps table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE disqualification_traps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trap_code VARCHAR(50) NOT NULL UNIQUE,
                    trap_category VARCHAR(50) NOT NULL,
                    trap_title VARCHAR(255) NOT NULL,
                    trap_description TEXT NOT NULL,
                    detection_method TEXT,
                    first_occurrence_project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    prevention_checklist_item TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (trap_category IN ('signature','seal','qualification','price','format','timing'))
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='disqualification_traps'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """All disqualification_traps columns are present."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE disqualification_traps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trap_code VARCHAR(50) NOT NULL UNIQUE,
                    trap_category VARCHAR(50) NOT NULL,
                    trap_title VARCHAR(255) NOT NULL,
                    trap_description TEXT NOT NULL,
                    detection_method TEXT,
                    first_occurrence_project_id INTEGER,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    prevention_checklist_item TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(disqualification_traps)"))}
        required_cols = {
            'id', 'trap_code', 'trap_category', 'trap_title', 'trap_description',
            'detection_method', 'first_occurrence_project_id', 'occurrence_count',
            'prevention_checklist_item', 'is_active', 'created_at'
        }
        assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

    def test_trap_code_unique(self, db_engine):
        """trap_code UNIQUE constraint works."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE disqualification_traps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trap_code VARCHAR(50) NOT NULL UNIQUE,
                    trap_category VARCHAR(50) NOT NULL,
                    trap_title VARCHAR(255) NOT NULL,
                    trap_description TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (trap_category IN ('signature','seal','qualification','price','format','timing'))
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO disqualification_traps (trap_code, trap_category, trap_title, trap_description) "
                "VALUES ('NO_SIGNATURE_PAGE', 'signature', 'Missing Signature Page', 'Signature page not found')"
            ))
            conn.commit()
            # Second insert with same trap_code should fail
            with pytest.raises(Exception):
                conn.execute(text(
                    "INSERT INTO disqualification_traps (trap_code, trap_category, trap_title, trap_description) "
                    "VALUES ('NO_SIGNATURE_PAGE', 'signature', 'Another', 'Another desc')"
                ))
                conn.commit()


class TestDraftRevivalsTable:
    def test_table_exists(self, db_engine):
        """draft_revivals table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE draft_revivals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abandoned_draft_id INTEGER NOT NULL REFERENCES abandoned_drafts(id) ON DELETE CASCADE,
                    new_project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    revival_type VARCHAR(50) NOT NULL,
                    revived_content TEXT,
                    adaptation_notes TEXT,
                    revived_by INTEGER REFERENCES users(id),
                    revived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_successful INTEGER,
                    CHECK (revival_type IN ('rebid_same_project','similar_project_reference'))
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='draft_revivals'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """All draft_revivals columns are present."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE draft_revivals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abandoned_draft_id INTEGER NOT NULL,
                    new_project_id INTEGER NOT NULL,
                    revival_type VARCHAR(50) NOT NULL,
                    revived_content TEXT,
                    adaptation_notes TEXT,
                    revived_by INTEGER,
                    revived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_successful INTEGER
                )
            """))
            conn.commit()
            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(draft_revivals)"))}
        required_cols = {
            'id', 'abandoned_draft_id', 'new_project_id', 'revival_type',
            'revived_content', 'adaptation_notes', 'revived_by', 'revived_at', 'is_successful'
        }
        assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

    def test_revival_type_check(self, db_engine):
        """revival_type CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE draft_revivals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abandoned_draft_id INTEGER NOT NULL,
                    new_project_id INTEGER NOT NULL,
                    revival_type VARCHAR(50) NOT NULL,
                    revived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_successful INTEGER,
                    CHECK (revival_type IN ('rebid_same_project','similar_project_reference'))
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO draft_revivals (abandoned_draft_id, new_project_id, revival_type) "
                "VALUES (1, 1, 'rebid_same_project')"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT revival_type FROM draft_revivals WHERE id=1"
            )).fetchone()
        assert result[0] == 'rebid_same_project'


class TestKnowledgeEvolutionLogsTable:
    def test_table_exists(self, db_engine):
        """knowledge_evolution_logs table can be created."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE knowledge_evolution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
                    action_type VARCHAR(50) NOT NULL,
                    project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                    old_quality_score INTEGER,
                    new_quality_score INTEGER,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (action_type IN ('created','weighted','deprecated','reused','confirmed_win','confirmed_lose'))
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_evolution_logs'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """All knowledge_evolution_logs columns are present."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE knowledge_evolution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    project_id INTEGER,
                    old_quality_score INTEGER,
                    new_quality_score INTEGER,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(knowledge_evolution_logs)"))}
        required_cols = {
            'id', 'chunk_id', 'action_type', 'project_id',
            'old_quality_score', 'new_quality_score', 'reason', 'created_at'
        }
        assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

    def test_action_type_check(self, db_engine):
        """action_type CHECK constraint accepts valid values."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE knowledge_evolution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    project_id INTEGER,
                    old_quality_score INTEGER,
                    new_quality_score INTEGER,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (action_type IN ('created','weighted','deprecated','reused','confirmed_win','confirmed_lose'))
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO knowledge_evolution_logs (chunk_id, action_type, project_id) "
                "VALUES (1, 'confirmed_win', 1)"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT action_type FROM knowledge_evolution_logs WHERE id=1"
            )).fetchone()
        assert result[0] == 'confirmed_win'


class TestCascadeDelete:
    def test_cascade_delete_project_removes_bid_outcomes(self, db_engine):
        """ON DELETE CASCADE removes bid_outcomes when project deleted."""
        with db_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("""
                CREATE TABLE bid_outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    outcome_status VARCHAR(20) NOT NULL,
                    outcome_date DATE NOT NULL,
                    final_bid_price NUMERIC(15, 2) NOT NULL,
                    is_manual_error INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (outcome_status IN ('win','lose','disqualified','abandoned','withdrawn'))
                )
            """))
            conn.commit()
            conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test', 'uploaded')"))
            conn.execute(text(
                "INSERT INTO bid_outcomes (project_id, outcome_status, outcome_date, final_bid_price) "
                "VALUES (1, 'win', '2026-01-01', 100000.00)"
            ))
            conn.commit()
            conn.execute(text("DELETE FROM projects WHERE id=1"))
            conn.commit()
            result = conn.execute(text(
                "SELECT COUNT(*) FROM bid_outcomes WHERE project_id=1"
            )).fetchone()
        assert result[0] == 0

    def test_cascade_delete_project_removes_winning_dna(self, db_engine):
        """ON DELETE CASCADE removes winning_dna when project deleted."""
        with db_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("""
                CREATE TABLE winning_dna (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    dna_type VARCHAR(50) NOT NULL,
                    score_contribution INTEGER NOT NULL,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (dna_type IN ('high_score_response','winning_price_strategy','effective_case_usage','format_excellence')),
                    CHECK (score_contribution BETWEEN 1 AND 10)
                )
            """))
            conn.commit()
            conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test', 'uploaded')"))
            conn.execute(text(
                "INSERT INTO winning_dna (project_id, dna_type, score_contribution) "
                "VALUES (1, 'winning_price_strategy', 8)"
            ))
            conn.commit()
            conn.execute(text("DELETE FROM projects WHERE id=1"))
            conn.commit()
            result = conn.execute(text(
                "SELECT COUNT(*) FROM winning_dna WHERE project_id=1"
            )).fetchone()
        assert result[0] == 0

    def test_cascade_delete_project_removes_draft_revivals(self, db_engine):
        """ON DELETE CASCADE removes draft_revivals when project deleted."""
        with db_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.execute(text("""
                CREATE TABLE draft_revivals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    abandoned_draft_id INTEGER NOT NULL REFERENCES abandoned_drafts(id) ON DELETE CASCADE,
                    new_project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    revival_type VARCHAR(50) NOT NULL,
                    revived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_successful INTEGER,
                    CHECK (revival_type IN ('rebid_same_project','similar_project_reference'))
                )
            """))
            conn.commit()
            conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test', 'uploaded')"))
            conn.execute(text(
                "INSERT INTO abandoned_drafts (id, project_id, can_be_revived) VALUES (1, 1, 1)"
            ))
            conn.execute(text(
                "INSERT INTO draft_revivals (abandoned_draft_id, new_project_id, revival_type) "
                "VALUES (1, 1, 'rebid_same_project')"
            ))
            conn.commit()
            conn.execute(text("DELETE FROM projects WHERE id=1"))
            conn.commit()
            result = conn.execute(text(
                "SELECT COUNT(*) FROM draft_revivals WHERE new_project_id=1"
            )).fetchone()
        assert result[0] == 0
