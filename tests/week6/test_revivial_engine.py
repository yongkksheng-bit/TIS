"""TDD tests for DraftRevivalEngine."""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.week6_review.revival_engine import DraftRevivalEngine
from app.models.formal_review import AbandonedDraft
from app.models.review import DraftRevival
from app.models.project import Project


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


class TestDraftRevivalEngineDefensive:
    """Defensive exception tests - MUST pass."""

    def test_revive_draft_raises_when_not_revivable(self, db_session):
        """Draft with can_be_revived=False must raise ValueError immediately."""
        # Create user
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        # Create project
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'evaluation_ready')"
        ))
        # Create abandoned draft with can_be_revived=False
        db_session.execute(text("""
            INSERT INTO abandoned_drafts (id, project_id, can_be_revived, archived_at)
            VALUES (1, 1, 0, CURRENT_TIMESTAMP)
        """))
        db_session.commit()

        engine = DraftRevivalEngine(db_session, draft_id=1)

        with pytest.raises(ValueError) as exc_info:
            engine.revive_draft(user_id=1, reason="Test reason")

        assert "non-revivable" in str(exc_info.value).lower()

    def test_revive_draft_raises_when_expired(self, db_session):
        """Draft archived more than 12 months ago must raise ValueError."""
        # Create user
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        # Create project
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'evaluation_ready')"
        ))
        # Create abandoned draft with archived_at > 12 months ago
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        db_session.execute(text("""
            INSERT INTO abandoned_drafts (id, project_id, can_be_revived, archived_at)
            VALUES (1, 1, 1, :archived_at)
        """), {"archived_at": old_date.isoformat()})
        db_session.commit()

        engine = DraftRevivalEngine(db_session, draft_id=1)

        with pytest.raises(ValueError) as exc_info:
            engine.revive_draft(user_id=1, reason="Test reason")

        assert "12 months" in str(exc_info.value)

    def test_revive_draft_raises_when_not_found(self, db_session):
        """Non-existent draft must raise ValueError."""
        engine = DraftRevivalEngine(db_session, draft_id=999)

        with pytest.raises(ValueError) as exc_info:
            engine.revive_draft(user_id=1, reason="Test reason")

        assert "not found" in str(exc_info.value).lower()


class TestDraftRevivalEnginePositive:
    """Positive path tests."""

    def test_revive_draft_success_sets_flags(self, db_session):
        """Successful revival sets revived_at, revived_to_project_id, can_be_revived=False."""
        # Create user
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        # Create project
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'terminated_by_boss')"
        ))
        # Create abandoned draft (archived 30 days ago, can_be_revived=True)
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO abandoned_drafts (id, project_id, can_be_revived, archived_at)
            VALUES (1, 1, 1, :archived_at)
        """), {"archived_at": recent_date.isoformat()})
        db_session.commit()

        engine = DraftRevivalEngine(db_session, draft_id=1)
        result = engine.revive_draft(user_id=1, reason="Rebid reason")

        # Check result
        assert result["revival_id"] is not None
        assert result["message"] is not None

        # Verify in database
        draft = db_session.execute(text(
            "SELECT revived_at, revived_to_project_id, can_be_revived FROM abandoned_drafts WHERE id=1"
        )).fetchone()

        assert draft[0] is not None  # revived_at set
        assert draft[1] == 1  # revived_to_project_id = original project id
        assert draft[2] == 0  # can_be_revived = False

    def test_revive_draft_creates_draft_revival_record(self, db_session):
        """Revival creates a draft_revivals table record."""
        # Create user
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        # Create project
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'terminated_by_boss')"
        ))
        # Create abandoned draft
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO abandoned_drafts (id, project_id, can_be_revived, archived_at)
            VALUES (1, 1, 1, :archived_at)
        """), {"archived_at": recent_date.isoformat()})
        db_session.commit()

        engine = DraftRevivalEngine(db_session, draft_id=1)
        result = engine.revive_draft(user_id=1, reason="Rebid reason")

        # Check draft_revivals record exists
        revival = db_session.execute(text(
            "SELECT abandoned_draft_id, new_project_id, revival_type, revived_by, adaptation_notes FROM draft_revivals WHERE id=:id"
        ), {"id": result["revival_id"]}).fetchone()

        assert revival is not None
        assert revival[0] == 1  # abandoned_draft_id
        assert revival[1] == 1  # new_project_id (same as original)
        assert revival[2] == "rebid_same_project"
        assert revival[3] == 1  # revived_by
        assert revival[4] == "Rebid reason"

    def test_revive_draft_restores_project_status(self, db_session):
        """Revived project status is set to 'evaluation_ready'."""
        # Create user
        db_session.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        # Create project in terminated state
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'terminated_by_boss')"
        ))
        # Create abandoned draft
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)
        db_session.execute(text("""
            INSERT INTO abandoned_drafts (id, project_id, can_be_revived, archived_at)
            VALUES (1, 1, 1, :archived_at)
        """), {"archived_at": recent_date.isoformat()})
        db_session.commit()

        engine = DraftRevivalEngine(db_session, draft_id=1)
        engine.revive_draft(user_id=1, reason="Rebid reason")

        # Check project status
        project = db_session.execute(text(
            "SELECT status FROM projects WHERE id=1"
        )).fetchone()

        assert project[0] == "evaluation_ready"
