"""TDD tests for BidReviewEngine."""
import pytest
import json
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.week6_review.review_engine import BidReviewEngine


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
                boss_final_price NUMERIC(15, 2) NOT NULL,
                boss_decision_reason TEXT,
                deviation_from_system NUMERIC(5, 4),
                deviation_reason_category VARCHAR(50),
                budget_limit NUMERIC(15, 2),
                is_under_limit INTEGER,
                limit_violation_warning TEXT,
                game_theory_analysis TEXT,
                status VARCHAR(20) DEFAULT 'decided'
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
        conn.commit()
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a new database session for a test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


class TestBidReviewEngine:
    """Test suite for BidReviewEngine."""

    def test_log_outcome_raises_for_invalid_project(self, db_session):
        """Non-existent project must raise ValueError."""
        engine = BidReviewEngine(db_session, project_id=999)

        with pytest.raises(ValueError) as exc_info:
            engine.log_outcome(is_win=True, competitor_price=100.0, feedback="", outcome_status="win")

        assert "not found" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_log_outcome_win_creates_winning_dna(self, db_session):
        """Win outcome creates WinningDNA records from tech proposal sections."""
        # Setup: create user, project, tech proposal with sections
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        db_session.execute(text("""
            INSERT INTO tech_proposal_tasks (id, project_id, generation_mode, input_config, generated_content, status, confirmed_at)
            VALUES (1, 1, 'auto', '{}', '{"sections": [{"title": "第一章 技术方案", "content": "..."}, {"title": "第二章 项目管理", "content": "..."}]}', 'confirmed', CURRENT_TIMESTAMP)
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        result = engine.log_outcome(is_win=True, competitor_price=26.0, feedback="", outcome_status="win")

        assert result["outcome_type"] == "win"
        assert result["dna_count"] == 2  # 2 sections from tech proposal

        # Verify winning_dna records
        dna_records = db_session.execute(text("SELECT dna_type, score_contribution, scoring_item_matched FROM winning_dna WHERE project_id=1")).fetchall()
        assert len(dna_records) == 2

    def test_log_outcome_win_creates_price_history(self, db_session):
        """Win outcome creates PriceHistory record."""
        # Setup
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        result = engine.log_outcome(is_win=True, competitor_price=26.0, feedback="", outcome_status="win")

        # Verify price_history record
        price_hist = db_session.execute(text("SELECT project_type, region, our_bid_price, winning_price, is_our_win FROM price_history")).fetchone()
        assert price_hist is not None
        assert price_hist[2] == 25.0  # our_bid_price
        assert price_hist[3] == 26.0  # winning_price
        assert price_hist[4] == 1  # is_our_win

    def test_log_outcome_win_creates_knowledge_evolution_logs(self, db_session):
        """Win outcome creates KnowledgeEvolutionLog records."""
        # Setup
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO knowledge_chunks (id, chunk_type, content, chunk_metadata, source_project_id) VALUES (1, 'section', 'Test content', '{}', 1)"))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        db_session.execute(text("""
            INSERT INTO tech_proposal_tasks (id, project_id, generation_mode, input_config, generated_content, status, confirmed_at)
            VALUES (1, 1, 'auto', '{}', '{"sections": [{"title": "技术方案", "content": "..."}]}', 'confirmed', CURRENT_TIMESTAMP)
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        engine.log_outcome(is_win=True, competitor_price=26.0, feedback="", outcome_status="win")

        # Verify knowledge_evolution_logs
        logs = db_session.execute(text("SELECT action_type, project_id, reason FROM knowledge_evolution_logs WHERE project_id=1")).fetchall()
        assert len(logs) >= 1
        assert any(log[0] == "confirmed_win" for log in logs)

    def test_log_outcome_disqualified_creates_trap(self, db_session):
        """Disqualification creates DisqualificationTrap record."""
        # Setup
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        result = engine.log_outcome(
            is_win=False,
            competitor_price=None,
            feedback="Missing signature page in bid document",
            outcome_status="disqualified"
        )

        assert result["outcome_type"] == "disqualification"
        assert result["trap_id"] is not None

        # Verify trap record
        trap = db_session.execute(text("SELECT trap_title, trap_category, occurrence_count FROM disqualification_traps WHERE id=:id"), {"id": result["trap_id"]}).fetchone()
        assert trap is not None
        assert "Missing signature" in trap[0]
        assert trap[2] == 1  # occurrence_count

    def test_log_outcome_disqualified_detects_manual_error(self, db_session):
        """Disqualification detects manual error from FormalReviewItem with fatal risk_level."""
        # Setup: project with fatal formal review item deleted by specialist
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        # Create fatal formal review item that was deleted by specialist
        db_session.execute(text("""
            INSERT INTO formal_review_items (id, project_id, source_type, check_category, check_title, system_status, specialist_status, risk_level)
            VALUES (1, 1, 'system_parsed', 'formal_compliance', 'Missing signature', 'failed', 'deleted', 'fatal')
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        result = engine.log_outcome(
            is_win=False,
            competitor_price=None,
            feedback="Fatal formal error",
            outcome_status="disqualified"
        )

        assert result["outcome_type"] == "disqualification"
        assert result["is_manual_error"] is True

        # Verify bid_outcome has is_manual_error=True
        outcome = db_session.execute(text("SELECT is_manual_error, disqualification_reason FROM bid_outcomes WHERE project_id=1")).fetchone()
        assert outcome[0] == 1  # is_manual_error
        assert outcome[1] == "Fatal formal error"

    def test_log_outcome_lose_records_to_price_history(self, db_session):
        """Lose outcome records to price_history when competitor_price is provided."""
        # Setup
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        result = engine.log_outcome(
            is_win=False,
            competitor_price=24.0,
            feedback="",
            outcome_status="lose"
        )

        assert result["outcome_type"] == "lose"
        assert result["competitor_price"] == 24.0

        # Verify price_history record
        price_hist = db_session.execute(text("SELECT our_bid_price, winning_price, is_our_win FROM price_history")).fetchone()
        assert price_hist is not None
        assert price_hist[0] == 25.0  # our_bid_price
        assert price_hist[1] == 24.0  # winning_price (competitor)
        assert price_hist[2] == 0  # is_our_win = False

    def test_log_outcome_lose_creates_knowledge_evolution_log(self, db_session):
        """Lose outcome creates KnowledgeEvolutionLog record."""
        # Setup
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, region, status) "
            "VALUES (1, 'Test Project', 'food', 'north', 'completed')"
        ))
        db_session.execute(text("INSERT INTO knowledge_chunks (id, chunk_type, content, chunk_metadata, source_project_id) VALUES (1, 'section', 'Test content', '{}', 1)"))
        db_session.execute(text("INSERT INTO cost_estimates (id, project_id, food_cost, logistics_cost, labor_cost, management_cost, total_cost, is_confirmed) VALUES (1, 1, 10, 5, 3, 2, 20, 1)"))
        db_session.execute(text("""
            INSERT INTO pricing_decisions (id, project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, budget_limit, status)
            VALUES (1, 1, 1, 20.0, 22.0, 28.0, 25.0, 30.0, 'decided')
        """))
        db_session.commit()

        engine = BidReviewEngine(db_session, project_id=1)
        engine.log_outcome(is_win=False, competitor_price=24.0, feedback="", outcome_status="lose")

        # Verify knowledge_evolution_log
        logs = db_session.execute(text("SELECT action_type, project_id FROM knowledge_evolution_logs WHERE project_id=1")).fetchall()
        assert any(log[0] == "confirmed_lose" for log in logs)
