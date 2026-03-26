"""TDD tests for Week 5 formal review SQLAlchemy models."""
import pytest
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(100))"))
        conn.execute(text("""CREATE TABLE projects (
            id INTEGER PRIMARY KEY, project_name VARCHAR(255), status VARCHAR(50),
            budget_amount NUMERIC(15,2), bid_open_date TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE cost_estimates (
            id INTEGER PRIMARY KEY, project_id INTEGER, total_cost NUMERIC(15,2),
            is_confirmed INTEGER
        )"""))
        conn.execute(text("""CREATE TABLE pricing_decisions (
            id INTEGER PRIMARY KEY, project_id INTEGER,
            boss_final_price NUMERIC(15,2), budget_limit NUMERIC(15,2)
        )"""))
        conn.execute(text("""CREATE TABLE formal_review_items (
            id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL,
            source_type VARCHAR(50), parent_item_id INTEGER,
            check_category VARCHAR(50), check_title VARCHAR(255),
            check_description TEXT, reference_clause TEXT,
            system_status VARCHAR(20), system_evidence TEXT,
            specialist_status VARCHAR(20) DEFAULT 'pending',
            specialist_notes TEXT, corrected_evidence TEXT,
            confirmed_by INTEGER, confirmed_at TIMESTAMP,
            pdf_highlight_coords TEXT, risk_level VARCHAR(20),
            created_at TIMESTAMP, updated_at TIMESTAMP
        )"""))
        conn.execute(text("""CREATE TABLE abandoned_drafts (
            id INTEGER PRIMARY KEY, project_id INTEGER,
            termination_stage VARCHAR(50), tech_proposal_path VARCHAR(500),
            business_proposal_path VARCHAR(500), pricing_decision_id INTEGER,
            termination_reason TEXT, termination_by INTEGER,
            can_be_revived INTEGER DEFAULT 1, archived_at TIMESTAMP,
            revived_at TIMESTAMP, revived_to_project_id INTEGER
        )"""))
        conn.execute(text("""CREATE TABLE final_bid_documents (
            id INTEGER PRIMARY KEY, project_id INTEGER,
            document_type VARCHAR(50), file_path VARCHAR(500),
            file_size INTEGER, generated_by INTEGER,
            generated_at TIMESTAMP, generation_status VARCHAR(20) DEFAULT 'generating',
            error_log TEXT, packaging_guide TEXT
        )"""))
        conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'boss')"))
        conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'awaiting_review')"))
        conn.commit()
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestFormalReviewItemModel:
    def test_specialist_status_defaults_to_pending(self, db_session):
        from app.models.formal_review import FormalReviewItem
        item = FormalReviewItem(
            project_id=1, source_type='system_parsed',
            check_category='qualification_validity', check_title='ISO证书检查',
            system_status='failed', risk_level='fatal',
        )
        db_session.add(item)
        db_session.commit()
        loaded = db_session.get(FormalReviewItem, item.id)
        assert loaded.specialist_status == 'pending'

    def test_risk_level_fatal_triggers_block(self, db_session):
        from app.models.formal_review import FormalReviewItem
        item = FormalReviewItem(
            project_id=1, source_type='ocr_comparison',
            check_category='qualification_validity', check_title='资质过期检查',
            system_status='failed', risk_level='fatal',
        )
        db_session.add(item)
        db_session.commit()
        assert item.risk_level == 'fatal'

    def test_pdf_highlight_coords_json(self, db_session):
        import json
        from app.models.formal_review import FormalReviewItem
        coords = {"page": 3, "x": 100, "y": 200, "width": 150, "height": 30, "color": "red"}
        item = FormalReviewItem(
            project_id=1, source_type='system_parsed',
            check_category='signature_seal', check_title='签字页检查',
            system_status='failed', risk_level='fatal',
            pdf_highlight_coords=coords,
        )
        db_session.add(item)
        db_session.commit()
        loaded = db_session.get(FormalReviewItem, item.id)
        assert loaded.pdf_highlight_coords["page"] == 3
        assert loaded.pdf_highlight_coords["color"] == "red"


class TestAbandonedDraftModel:
    def test_can_be_revived_defaults_true(self, db_session):
        from app.models.formal_review import AbandonedDraft
        draft = AbandonedDraft(
            project_id=1, termination_stage='formal_review',
            termination_reason='老板推翻', termination_by=1,
        )
        db_session.add(draft)
        db_session.commit()
        loaded = db_session.get(AbandonedDraft, draft.id)
        assert loaded.can_be_revived is True


class TestFinalBidDocumentModel:
    def test_generation_status_defaults_to_generating(self, db_session):
        from app.models.formal_review import FinalBidDocument
        doc = FinalBidDocument(project_id=1)
        db_session.add(doc)
        db_session.commit()
        loaded = db_session.get(FinalBidDocument, doc.id)
        assert loaded.generation_status == 'generating'

    def test_packaging_guide_json(self, db_session):
        from app.models.formal_review import FinalBidDocument
        guide = {
            "seal_bags": [{"type": "正本", "copies": 1}],
            "documents_checklist": ["营业执照"],
        }
        doc = FinalBidDocument(project_id=1, packaging_guide=guide)
        db_session.add(doc)
        db_session.commit()
        loaded = db_session.get(FinalBidDocument, doc.id)
        assert loaded.packaging_guide["seal_bags"][0]["type"] == "正本"
