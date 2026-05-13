"""Tests for Week 5 formal review API endpoints."""
import pytest
import json
from datetime import datetime, timedelta, date
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db


# ─── In-memory test DB setup ───────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def setup_tables(conn):
    """Create all required tables for testing."""
    conn.execute(text("PRAGMA foreign_keys = ON"))

    # users
    conn.execute(text("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) NOT NULL UNIQUE
        )
    """))

    # projects
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

    # cost_estimates
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
            estimated_by INTEGER,
            estimate_reason TEXT,
            is_confirmed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # pricing_decisions
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

    # formal_review_items
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # abandoned_drafts
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

    # final_bid_documents
    conn.execute(text("""
        CREATE TABLE final_bid_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            document_type VARCHAR(50),
            file_path VARCHAR(500),
            file_size INTEGER,
            generated_by INTEGER REFERENCES users(id),
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            generation_status VARCHAR(20) NOT NULL DEFAULT 'generating',
            error_log TEXT,
            packaging_guide TEXT
        )
    """))

    # tender_documents (needed for formal review engine)
    conn.execute(text("""
        CREATE TABLE tender_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            file_path VARCHAR(500),
            file_type VARCHAR(10),
            parsing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            extracted_data TEXT,
            parsed_by_ai INTEGER NOT NULL DEFAULT 0,
            confirmed_by_human INTEGER NOT NULL DEFAULT 0,
            plan_code VARCHAR(50),
            agency_project_code VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id)
        )
    """))

    # standard_certifications
    conn.execute(text("""
        CREATE TABLE standard_certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_code VARCHAR(50) UNIQUE NOT NULL,
            cert_full_name VARCHAR(255) NOT NULL,
            cert_short_name VARCHAR(100),
            aliases TEXT,
            required_keywords TEXT NOT NULL,
            exclude_keywords TEXT NOT NULL,
            cert_number_pattern VARCHAR(100),
            issuing_authority_keywords TEXT,
            category VARCHAR(50),
            validity_years INTEGER,
            is_mandatory_for_food_delivery INTEGER NOT NULL DEFAULT 0,
            is_mandatory_for_property INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # ocr_extractions
    conn.execute(text("""
        CREATE TABLE ocr_extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            field_name VARCHAR(50) NOT NULL,
            field_value TEXT,
            confidence_score NUMERIC(4, 3),
            normalized_value TEXT,
            standard_cert_id INTEGER REFERENCES standard_certifications(id) ON DELETE SET NULL,
            is_validated INTEGER NOT NULL DEFAULT 0,
            validated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            validation_notes TEXT,
            raw_text TEXT,
            bbox_coords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))


def seed_base_data(conn):
    """Seed basic test data: user, project."""
    conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
    bid_date = (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(text("""
        INSERT INTO projects (id, project_name, project_type, status, budget_amount,
         relationship_flag, owner_unit, region, bid_open_date)
        VALUES (1, '测试项目', 'food', 'approved_by_specialist', 1500000, 0, '某政府', '北京', :bid_date)
    """), {"bid_date": bid_date})
    conn.execute(text("""
        INSERT INTO projects (id, project_name, project_type, status, budget_amount,
         relationship_flag, owner_unit, region, bid_open_date)
        VALUES (2, '测试项目2', 'food', 'approved_by_specialist', 2000000, 0, '某企业', '上海', :bid_date)
    """), {"bid_date": bid_date})
    conn.commit()


def override_get_db():
    """Override get_db to use test database."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Tests ─────────────────────────────────────────────────────────────────

class TestFormalReviewAPI:
    """Test suite for formal review API endpoints."""

    client = TestClient(app)

    @classmethod
    def setup_class(cls):
        """Set up test database once for all tests."""
        with test_engine.connect() as conn:
            setup_tables(conn)
            seed_base_data(conn)

    def setup_method(self):
        """Clean formal_review_items before each test."""
        with test_engine.connect() as conn:
            conn.execute(text("DELETE FROM formal_review_items"))
            conn.execute(text("DELETE FROM abandoned_drafts"))
            conn.execute(text("DELETE FROM final_bid_documents"))
            conn.commit()

    # ─── 1. test_initiate_review_creates_checklist ─────────────────────────

    def test_initiate_review_creates_checklist(self):
        """POST /api/v1/projects/{project_id}/formal-review/initiate → 200."""
        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                "/api/v1/projects/1/formal-review/initiate"
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert "total_items" in data
            assert "fatal_count" in data
            assert data["total_items"] >= 0
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 2. test_get_review_items_returns_list ─────────────────────────────

    def test_get_review_items_returns_list(self):
        """GET /api/v1/projects/{project_id}/formal-review/items → 200."""
        # Seed an item first
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价合规检查', 'passed', 'info', 'pending')
            """))
            conn.commit()

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.get("/api/v1/projects/1/formal-review/items")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 1
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 3. test_confirm_item_sets_status_to_confirmed ─────────────────────

    def test_confirm_item_sets_status_to_confirmed(self):
        """POST /api/v1/formal-review-items/{item_id}/confirm → specialist_status='confirmed'."""
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价合规检查', 'passed', 'info', 'pending')
            """))
            conn.commit()
            result = conn.execute(text("SELECT last_insert_rowid()")).fetchone()
            item_id = result[0]

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                f"/api/v1/formal-review-items/{item_id}/confirm",
                json={"notes": "确认通过"}
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["specialist_status"] == "confirmed"
            assert data["confirmed_by"] == 1
            assert data["confirmed_at"] is not None
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 4. test_correct_item_sets_status_to_corrected ─────────────────────

    def test_correct_item_sets_status_to_corrected(self):
        """POST /api/v1/formal-review-items/{item_id}/correct → specialist_status='corrected'."""
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价合规检查', 'failed', 'fatal', 'pending')
            """))
            conn.commit()
            result = conn.execute(text("SELECT last_insert_rowid()")).fetchone()
            item_id = result[0]

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                f"/api/v1/formal-review-items/{item_id}/correct",
                json={
                    "corrected_status": "passed",
                    "corrected_evidence": "第5页修正说明",
                    "notes": "已修正"
                }
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["specialist_status"] == "corrected"
            assert data["corrected_evidence"] == "第5页修正说明"
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 5. test_delete_item_sets_status_to_deleted ────────────────────────

    def test_delete_item_sets_status_to_deleted(self):
        """POST /api/v1/formal-review-items/{item_id}/delete → specialist_status='deleted'."""
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价合规检查', 'passed', 'info', 'pending')
            """))
            conn.commit()
            result = conn.execute(text("SELECT last_insert_rowid()")).fetchone()
            item_id = result[0]

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                f"/api/v1/formal-review-items/{item_id}/delete",
                json={"notes": "不需要此项"}
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["specialist_status"] == "deleted"
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 6. test_manual_add_creates_item ───────────────────────────────────

    def test_manual_add_creates_item(self):
        """POST /api/v1/projects/{project_id}/formal-review/manual-add → new item created."""
        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                "/api/v1/projects/1/formal-review/manual-add",
                json={
                    "check_category": "manual_check",
                    "check_title": "人工检查项",
                    "check_description": "手动添加的检查项",
                    "risk_level": "warning",
                    "reference_clause": "招标文件第3.2条"
                }
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert "id" in data
            assert data["source_type"] == "manual_added"
            assert data["check_title"] == "人工检查项"
            assert data["risk_level"] == "warning"
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 7. test_status_shows_fatal_pending ────────────────────────────────

    def test_status_shows_fatal_pending(self):
        """Seed fatal pending item, GET status → fatal_pending > 0."""
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价超限', 'failed', 'fatal', 'pending')
            """))
            conn.commit()

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.get("/api/v1/projects/1/formal-review/status")
            assert response.status_code == 200
            data = response.json()
            assert data["fatal_pending"] >= 1
            assert data["can_generate"] is False
            assert data["blocking_reason"] is not None
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 8. test_generate_blocked_when_fatal_pending ───────────────────────

    def test_generate_blocked_when_fatal_pending(self):
        """POST /api/v1/projects/{project_id}/final-documents/generate → 400 when fatal pending."""
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价超限', 'failed', 'fatal', 'pending')
            """))
            conn.commit()

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                "/api/v1/projects/1/final-documents/generate",
                json={}
            )
            assert response.status_code == 400
            assert "致命风险" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 9. test_generate_allowed_when_no_fatal_pending ─────────────────────

    def test_generate_allowed_when_no_fatal_pending(self):
        """All items confirmed, POST generate → 200."""
        # Seed confirmed items only
        with test_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO formal_review_items
                (project_id, source_type, check_category, check_title, system_status, risk_level, specialist_status)
                VALUES (1, 'system_parsed', 'price_compliance', '报价合规', 'passed', 'info', 'confirmed')
            """))
            conn.execute(text("""
                INSERT INTO cost_estimates
                (project_id, version_number, food_cost, logistics_cost, labor_cost, management_cost,
                 other_cost, total_cost, estimated_by, is_confirmed)
                VALUES (1, 1, 100000, 50000, 300000, 200000, 50000, 700000, 1, 1)
            """))
            conn.execute(text("""
                INSERT INTO pricing_decisions
                (project_id, cost_estimate_id, cost_base, system_suggested_low, system_suggested_high,
                 system_suggested_optimal, finance_suggested_price, boss_final_price, boss_decision_reason,
                 deviation_from_system, deviation_reason_category, budget_limit, is_under_limit, status)
                VALUES (1, 1, 700000, 714000, 805000, 750000, 730000, 740000, '合理定价', 0.05, 'normal', 1500000, 1, 'decided')
            """))
            conn.execute(text("""
                INSERT INTO tech_proposal_tasks
                (project_id, generation_mode, input_config, generated_content, status, created_by)
                VALUES (1, 'ai', '{}', '{"sections": [{"section_title": "项目概述", "content": "测试内容"}]}', 'confirmed', 1)
            """))
            conn.commit()

        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                "/api/v1/projects/1/final-documents/generate",
                json={}
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["generation_status"] == "completed"
            assert "file_path" in data
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 10. test_abandon_archives_to_abandoned_drafts ──────────────────────

    def test_abandon_archives_to_abandoned_drafts(self):
        """POST /api/v1/projects/{project_id}/abandon → record created in abandoned_drafts."""
        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.post(
                "/api/v1/projects/1/abandon",
                json={"reason": "客户终止", "user_id": 1}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["termination_stage"] == "formal_review"
            assert data["termination_reason"] == "客户终止"

            # Verify DB record
            with test_engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT * FROM abandoned_drafts WHERE project_id = 1"
                )).fetchone()
                assert row is not None
                # row is a tuple in SQLite; termination_reason is column index 6
                assert row[6] == "客户终止"
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── 11. test_review_status_response_structure ──────────────────────────

    def test_review_status_response_structure(self):
        """GET /api/v1/projects/{project_id}/formal-review/status → has required fields."""
        app.dependency_overrides[get_db] = override_get_db
        try:
            response = self.client.get("/api/v1/projects/1/formal-review/status")
            assert response.status_code == 200
            data = response.json()
            assert "project_id" in data
            assert "total_items" in data
            assert "confirmed_items" in data
            assert "fatal_pending" in data
            assert "warning_pending" in data
            assert "can_generate" in data
            assert "blocking_reason" in data
        finally:
            app.dependency_overrides.pop(get_db, None)
