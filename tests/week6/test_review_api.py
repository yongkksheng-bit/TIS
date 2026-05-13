"""TDD tests for Week 6 Review API endpoints."""
import pytest
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(100) NOT NULL UNIQUE)"))
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
                relation_identifier VARCHAR(50),
                differentiation_guidance VARCHAR(1000),
                generation_mode VARCHAR(20),
                is_retender INTEGER NOT NULL DEFAULT 0,
                parent_project_id INTEGER,
                plan_code VARCHAR(50),
                agency_project_code VARCHAR(100),
                is_deleted INTEGER NOT NULL DEFAULT 0,
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
                pricing_decision_id INTEGER REFERENCES pricing_decisions(id),
                termination_reason TEXT,
                termination_by INTEGER REFERENCES users(id),
                can_be_revived INTEGER NOT NULL DEFAULT 1,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revived_at TIMESTAMP,
                revived_to_project_id INTEGER REFERENCES projects(id)
            )
        """))
        conn.execute(text("""
            CREATE TABLE cost_estimates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                version_number INTEGER DEFAULT 1,
                food_cost NUMERIC(15, 2) NOT NULL,
                logistics_cost NUMERIC(15, 2) NOT NULL,
                labor_cost NUMERIC(15, 2) NOT NULL,
                management_cost NUMERIC(15, 2) NOT NULL,
                other_cost NUMERIC(15, 2) DEFAULT 0,
                total_cost NUMERIC(15, 2) NOT NULL,
                estimated_by INTEGER REFERENCES users(id),
                estimate_reason TEXT,
                is_confirmed INTEGER DEFAULT 0
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
                boss_final_price NUMERIC(15, 2),
                boss_decision_reason TEXT,
                deviation_from_system NUMERIC(5, 4),
                deviation_reason_category VARCHAR(50),
                budget_limit NUMERIC(15, 2),
                is_under_limit INTEGER,
                limit_violation_warning TEXT,
                game_theory_analysis TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'decided',
                specialist_price NUMERIC(15, 2),
                specialist_notes TEXT,
                action_type VARCHAR(30),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
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
        conn.execute(text("""
            CREATE TABLE price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id),
                project_type VARCHAR(100),
                region VARCHAR(100),
                budget_amount NUMERIC(15, 2),
                our_cost NUMERIC(15, 2),
                our_bid_price NUMERIC(15, 2),
                winning_price NUMERIC(15, 2),
                winning_unit VARCHAR(255),
                discount_rate NUMERIC(5, 4),
                bid_date DATE,
                is_our_win INTEGER,
                data_source VARCHAR(50)
            )
        """))
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
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
                confirmed_by INTEGER REFERENCES users(id)
            )
        """))
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE knowledge_evolution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
                action_type VARCHAR(50) NOT NULL,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                old_quality_score INTEGER,
                new_quality_score INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
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
                is_successful INTEGER
            )
        """))
        conn.commit()
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a new database session for a test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    """Create a TestClient with database override."""
    from app.main import app
    from app.dependencies import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def setup_basic_project(db_session):
    """Setup basic project with pricing decision."""
    db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
    db_session.execute(text(
        "INSERT INTO projects (id, project_name, project_type, region, status, owner_unit) "
        "VALUES (1, 'Test Project', 'food', 'north', 'completed', '测试单位')"
    ))
    db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
    db_session.execute(text("""
        INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
        VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
    """))
    db_session.commit()


# ─── Test Record Outcome ────────────────────────────────────────────────────

class TestRecordOutcome:
    """Test POST /api/v1/projects/{project_id}/outcomes/record"""

    def test_record_win(self, client, db_session, setup_basic_project):
        """Record a winning bid outcome."""
        response = client.post(
            "/api/v1/projects/1/outcomes/record",
            json={
                "outcome_status": "win",
                "outcome_date": "2026-03-26",
                "final_bid_price": 1500000.0,
                "winning_price": 1480000.0,
                "winning_unit": "竞争公司",
                "our_price_rank": 1,
                "extract_dna": True,
                "update_traps": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["outcome_status"] == "win"
        # Note: final_bid_price comes from pricing_decision.boss_final_price, not request body
        assert data["data"]["final_bid_price"] == 25.0

    def test_record_lose(self, client, db_session, setup_basic_project):
        """Record a losing bid outcome."""
        response = client.post(
            "/api/v1/projects/1/outcomes/record",
            json={
                "outcome_status": "lose",
                "outcome_date": "2026-03-26",
                "final_bid_price": 1500000.0,
                "winning_price": 1480000.0,
                "winning_unit": "竞争公司",
                "our_price_rank": 2,
                "extract_dna": False,
                "update_traps": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["outcome_status"] == "lose"

    def test_record_disqualified(self, client, db_session, setup_basic_project):
        """Record a disqualified bid outcome."""
        response = client.post(
            "/api/v1/projects/1/outcomes/record",
            json={
                "outcome_status": "disqualified",
                "outcome_date": "2026-03-26",
                "final_bid_price": 1500000.0,
                "disqualification_reason": "Missing signature page",
                "disqualification_type": "fatal_formal",
                "extract_dna": False,
                "update_traps": True
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["outcome_status"] == "disqualified"
        assert data["data"]["disqualification_reason"] == "Missing signature page"

    def test_record_invalid_project(self, client, db_session):
        """Record outcome for non-existent project returns 404."""
        response = client.post(
            "/api/v1/projects/999/outcomes/record",
            json={
                "outcome_status": "win",
                "outcome_date": "2026-03-26",
                "final_bid_price": 1500000.0,
                "extract_dna": True,
                "update_traps": False
            }
        )
        assert response.status_code == 404


# ─── Test Review Analysis ───────────────────────────────────────────────────

class TestReviewAnalysis:
    """Test GET /api/v1/projects/{project_id}/review-analysis"""

    def test_get_analysis_not_found(self, client, db_session, setup_basic_project):
        """Get analysis for project with no outcome returns 404."""
        response = client.get("/api/v1/projects/1/review-analysis")
        assert response.status_code == 404

    def test_get_analysis_success(self, client, db_session, setup_basic_project):
        """Get analysis after recording outcome."""
        # First record an outcome
        client.post(
            "/api/v1/projects/1/outcomes/record",
            json={
                "outcome_status": "win",
                "outcome_date": "2026-03-26",
                "final_bid_price": 1500000.0,
                "extract_dna": True,
                "update_traps": False
            }
        )
        # Then get analysis
        response = client.get("/api/v1/projects/1/review-analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == 1
        assert data["outcome_status"] == "win"

    def test_get_analysis_invalid_project(self, client, db_session):
        """Get analysis for non-existent project returns 404."""
        response = client.get("/api/v1/projects/999/review-analysis")
        assert response.status_code == 404


# ─── Test Review Analysis Confirm ───────────────────────────────────────────

class TestReviewAnalysisConfirm:
    """Test POST /api/v1/projects/{project_id}/review-analysis/confirm"""

    def test_confirm_analysis(self, client, db_session, setup_basic_project):
        """Confirm review analysis and update notes."""
        # First record an outcome
        client.post(
            "/api/v1/projects/1/outcomes/record",
            json={
                "outcome_status": "win",
                "outcome_date": "2026-03-26",
                "final_bid_price": 1500000.0,
                "extract_dna": True,
                "update_traps": False
            }
        )
        # Confirm analysis
        response = client.post(
            "/api/v1/projects/1/review-analysis/confirm",
            json={
                "confirmed_analysis": {"winner": "us", "score": 95},
                "manual_notes": "专家确认无误",
                "extract_dna": True,
                "update_traps": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["review_notes"] == "专家确认无误"

    def test_confirm_analysis_no_outcome(self, client, db_session, setup_basic_project):
        """Confirm analysis when no outcome exists returns 404."""
        response = client.post(
            "/api/v1/projects/1/review-analysis/confirm",
            json={
                "confirmed_analysis": {"winner": "us"},
                "manual_notes": "专家确认",
                "extract_dna": True,
                "update_traps": False
            }
        )
        assert response.status_code == 404


# ─── Test Rebid Alert ───────────────────────────────────────────────────────

class TestRebidAlert:
    """Test GET /api/v1/projects/{project_id}/rebid-alert"""

    def test_rebid_alert_no_match(self, client, db_session, setup_basic_project):
        """No rebid alert when no similar historical project."""
        response = client.get("/api/v1/projects/1/rebid-alert")
        assert response.status_code == 200
        data = response.json()
        assert data["is_rebid"] is False
        assert data["warnings"] == []

    def test_rebid_alert_match_found(self, client, db_session):
        """Rebid alert when similar historical project found."""
        # Setup: create historical project with same owner_unit within 12 months
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, owner_unit, region, status, bid_open_date) "
            "VALUES (1, 'Historical Project', 'food', '测试单位', 'north', 'completed', '2025-08-01')"
        ))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, owner_unit, region, status, bid_open_date) "
            "VALUES (2, 'New Project', 'food', '测试单位', 'north', 'uploaded', '2026-03-01')"
        ))
        db_session.commit()

        response = client.get("/api/v1/projects/2/rebid-alert")
        assert response.status_code == 200
        data = response.json()
        assert data["is_rebid"] is True
        assert data["historical_project_id"] == 1


# ─── Test Revive Draft ───────────────────────────────────────────────────────

class TestReviveDraft:
    """Test POST /api/v1/revivals/{abandoned_draft_id}/revive-to/{new_project_id}"""

    def test_revive_success(self, client, db_session):
        """Successfully revive an abandoned draft."""
        # Setup: create project and abandoned draft
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status) "
            "VALUES (1, 'Original Project', 'food', 'terminated_by_boss')"
        ))
        db_session.execute(text(
            "INSERT INTO abandoned_drafts (id, project_id, termination_reason, can_be_revived, archived_at) "
            "VALUES (1, 1, '战略调整', 1, CURRENT_TIMESTAMP)"
        ))
        db_session.commit()

        response = client.post("/api/v1/revivals/1/revive-to/1")
        assert response.status_code == 200
        data = response.json()
        assert data["abandoned_draft_id"] == 1
        assert data["new_project_id"] == 1

    def test_revive_non_revivable_raises_400(self, client, db_session):
        """Reviving non-revivable draft raises 400."""
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status) "
            "VALUES (1, 'Original Project', 'food', 'terminated_by_boss')"
        ))
        db_session.execute(text(
            "INSERT INTO abandoned_drafts (id, project_id, termination_reason, can_be_revived, archived_at) "
            "VALUES (1, 1, '永久废弃', 0, CURRENT_TIMESTAMP)"
        ))
        db_session.commit()

        response = client.post("/api/v1/revivals/1/revive-to/1")
        assert response.status_code == 400
        assert "non-revivable" in response.json()["detail"].lower()

    def test_revive_expired_raises_400(self, client, db_session):
        """CRITICAL: Reviving expired draft (>12 months) raises 400."""
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status) "
            "VALUES (1, 'Original Project', 'food', 'terminated_by_boss')"
        ))
        # archived_at more than 12 months ago
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%d %H:%M:%S")
        db_session.execute(text(
            f"INSERT INTO abandoned_drafts (id, project_id, termination_reason, can_be_revived, archived_at) "
            f"VALUES (1, 1, '战略调整', 1, '{old_date}')"
        ))
        db_session.commit()

        response = client.post("/api/v1/revivals/1/revive-to/1")
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower() or "12 months" in response.json()["detail"].lower()

    def test_revive_not_found_raises_400(self, client, db_session):
        """Reviving non-existent draft raises 400."""
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status) "
            "VALUES (1, 'Original Project', 'food', 'terminated_by_boss')"
        ))
        db_session.commit()

        response = client.post("/api/v1/revivals/999/revive-to/1")
        assert response.status_code == 400


# ─── Test Knowledge Evolution Report ───────────────────────────────────────

class TestEvolutionReport:
    """Test GET /api/v1/knowledge-base/evolution-report"""

    def test_evolution_report(self, client, db_session):
        """Get knowledge base evolution stats."""
        # Setup: create some knowledge chunks
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status) "
            "VALUES (1, 'Test Project', 'food', 'completed')"
        ))
        db_session.execute(text(
            "INSERT INTO knowledge_chunks (id, chunk_type, content, chunk_metadata, source_project_id, is_deprecated) "
            "VALUES (1, 'section', 'Test content', '{\"quality_score\": 80}', 1, 0)"
        ))
        db_session.execute(text(
            "INSERT INTO knowledge_chunks (id, chunk_type, content, chunk_metadata, source_project_id, is_deprecated) "
            "VALUES (2, 'section', 'Test content 2', '{\"quality_score\": 60}', 1, 1)"
        ))
        db_session.execute(text(
            "INSERT INTO winning_dna (id, project_id, dna_type, score_contribution) "
            "VALUES (1, 1, 'high_score_response', 8)"
        ))
        db_session.execute(text(
            "INSERT INTO disqualification_traps (id, trap_code, trap_category, trap_title, trap_description, is_active) "
            "VALUES (1, 'TRAP_TEST_1', 'format', 'Test trap', 'Test description', 1)"
        ))
        db_session.commit()

        response = client.get("/api/v1/knowledge-base/evolution-report")
        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] >= 0
        assert data["weighted_by_wins"] >= 0
        assert data["new_traps_added"] >= 0
        assert data["avg_quality_score_trend"] in ['up', 'down', 'stable']
