import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.week3_rag.mode_switch_service import ModeSwitchService
from app.models.project import Project
from app.models.tech_proposal import TechProposalTask


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
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestModeSwitchService:
    def test_auto_to_guided_archives_existing_proposal(self, db_session):
        """Switching AUTO→GUIDED marks existing task as archived_due_to_mode_switch."""
        # Create project in AUTO mode with a task
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status, generation_mode, owner_unit, region) "
            "VALUES (1, '测试', 'food', 'approved_by_specialist', 'auto', '某政府', '北京')"
        ))
        db_session.execute(text(
            "INSERT INTO tech_proposal_tasks (project_id, generation_mode, status) "
            "VALUES (1, 'auto', 'completed')"
        ))
        db_session.commit()

        service = ModeSwitchService()
        result = service.switch_mode(db=db_session, project_id=1, new_mode='guided', operator_id=1)

        assert result['status'] == 'switched'
        assert result['old_mode'] == 'auto'
        assert result['new_mode'] == 'guided'

        # Verify task was archived
        task = db_session.query(TechProposalTask).filter_by(project_id=1).first()
        assert task.status == 'archived_due_to_mode_switch'

        # Verify project mode was updated
        project = db_session.get(Project, 1)
        assert project.generation_mode == 'guided'

    def test_guided_to_auto_discards_custom_content(self, db_session):
        """Switching GUIDED→AUTO marks task as discarded_due_to_mode_switch."""
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status, generation_mode, owner_unit, region) "
            "VALUES (1, '测试', 'food', 'approved_by_specialist', 'guided', '某政府', '北京')"
        ))
        db_session.execute(text(
            "INSERT INTO tech_proposal_tasks (project_id, generation_mode, status) "
            "VALUES (1, 'guided', 'completed')"
        ))
        db_session.commit()

        service = ModeSwitchService()
        result = service.switch_mode(db=db_session, project_id=1, new_mode='auto', operator_id=1)

        assert result['status'] == 'switched'
        assert result['old_mode'] == 'guided'
        assert result['new_mode'] == 'auto'

        task = db_session.query(TechProposalTask).filter_by(project_id=1).first()
        assert task.status == 'discarded_due_to_mode_switch'

        project = db_session.get(Project, 1)
        assert project.generation_mode == 'auto'

    def test_same_mode_returns_unchanged(self, db_session):
        """Switching to the same mode returns 'unchanged' without modifying anything."""
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status, generation_mode, owner_unit, region) "
            "VALUES (1, '测试', 'food', 'approved_by_specialist', 'auto', '某政府', '北京')"
        ))
        db_session.commit()

        service = ModeSwitchService()
        result = service.switch_mode(db=db_session, project_id=1, new_mode='auto', operator_id=1)

        assert result['status'] == 'unchanged'
        assert result['old_mode'] == 'auto'

    def test_no_existing_task_still_switches_mode(self, db_session):
        """If no task exists, switching mode still updates project.generation_mode."""
        db_session.execute(text(
            "INSERT INTO projects (id, project_name, project_type, status, generation_mode, owner_unit, region) "
            "VALUES (1, '测试', 'food', 'approved_by_specialist', 'auto', '某政府', '北京')"
        ))
        db_session.commit()

        service = ModeSwitchService()
        result = service.switch_mode(db=db_session, project_id=1, new_mode='guided', operator_id=1)

        assert result['status'] == 'switched'
        project = db_session.get(Project, 1)
        assert project.generation_mode == 'guided'

    def test_switch_mode_project_not_found_raises(self, db_session):
        """Non-existent project raises ValueError."""
        service = ModeSwitchService()
        with pytest.raises(ValueError) as exc_info:
            service.switch_mode(db=db_session, project_id=999, new_mode='auto', operator_id=1)
        assert 'not found' in str(exc_info.value).lower()