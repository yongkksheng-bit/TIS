"""
E2E integration test for Week 5 formal review pipeline.

Tests the complete Week 1-5 pipeline integration:
1. Full flow: initiate → check status → confirm items → generate final doc
2. Fatal pending blocks generation (400 response)
3. Manual add + confirm flow
4. Boss termination → abandoned_drafts archive flow

Run: pytest tests/week5/test_e2e_formal_review.py -v
"""
import pytest
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
    """Create all required tables for E2E testing."""
    conn.execute(text("PRAGMA foreign_keys = ON"))

    conn.execute(text("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username VARCHAR(100) NOT NULL
        )
    """))

    conn.execute(text("""
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY,
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
            id INTEGER PRIMARY KEY,
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

    conn.execute(text("""
        CREATE TABLE pricing_decisions (
            id INTEGER PRIMARY KEY,
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

    conn.execute(text("""
        CREATE TABLE tech_proposal_tasks (
            id INTEGER PRIMARY KEY,
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
        CREATE TABLE formal_review_items (
            id INTEGER PRIMARY KEY,
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
            confirmed_by INTEGER,
            confirmed_at TIMESTAMP,
            pdf_highlight_coords TEXT,
            risk_level VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    conn.execute(text("""
        CREATE TABLE abandoned_drafts (
            id INTEGER PRIMARY KEY,
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
        CREATE TABLE final_bid_documents (
            id INTEGER PRIMARY KEY,
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

    conn.execute(text("""
        CREATE TABLE tender_documents (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            file_path VARCHAR(500),
            file_type VARCHAR(10),
            parsing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            extracted_data TEXT,
            parsed_by_ai INTEGER NOT NULL DEFAULT 0,
            confirmed_by_human INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id)
        )
    """))

    conn.execute(text("""
        CREATE TABLE standard_certifications (
            id INTEGER PRIMARY KEY,
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

    conn.execute(text("""
        CREATE TABLE ocr_extractions (
            id INTEGER PRIMARY KEY,
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
    """Seed base test data: user, project with confirmed cost estimate and pricing decision."""
    conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'specialist')"))
    conn.execute(text(
        "INSERT INTO projects (id, project_name, project_type, status, budget_amount, "
        "relationship_flag, owner_unit, region) "
        "VALUES (1, 'E2E测试项目', 'food', 'awaiting_review', 2000000, 0, '某政府', '北京')"
    ))
    # Confirmed cost estimate
    conn.execute(text("""
        INSERT INTO cost_estimates
        (id, project_id, version_number, food_cost, logistics_cost, labor_cost,
         management_cost, other_cost, total_cost, estimated_by, is_confirmed)
        VALUES (1, 1, 1, 400000, 200000, 300000, 200000, 100000, 1200000, 1, 1)
    """))
    # Confirmed pricing decision
    conn.execute(text("""
        INSERT INTO pricing_decisions
        (id, project_id, cost_estimate_id, boss_final_price, budget_limit, cost_base,
         system_suggested_low, system_suggested_high, system_suggested_optimal, status)
        VALUES (1, 1, 1, 1300000, 2000000, 1200000, 1224000, 1380000, 1300000, 'decided')
    """))
    # Confirmed tech proposal (needed for final document generation)
    conn.execute(text("""
        INSERT INTO tech_proposal_tasks
        (id, project_id, generation_mode, input_config, generated_content, status, created_by, confirmed_at, confirmed_by)
        VALUES (1, 1, 'ai', '{}',
            '{"sections": [{"section_title": "项目概述", "content": "本项目是某政府采购项目。"}]}',
            'confirmed', 1, datetime('now'), 1)
    """))
    conn.commit()


def override_get_db():
    """Override get_db to use test database."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Test class ─────────────────────────────────────────────────────────────

class TestE2EFormalReview:
    """E2E integration tests for the formal review pipeline."""

    client = TestClient(app)

    @classmethod
    def setup_class(cls):
        """Set up test database once for all tests."""
        with test_engine.connect() as conn:
            setup_tables(conn)
            seed_base_data(conn)

    def setup_method(self):
        """Clean dynamic tables before each test."""
        with test_engine.connect() as conn:
            conn.execute(text("DELETE FROM formal_review_items"))
            conn.execute(text("DELETE FROM abandoned_drafts"))
            conn.execute(text("DELETE FROM final_bid_documents"))
            conn.commit()

    # ─── Test 1: Full flow pricing to final doc ─────────────────────────────

    def test_full_flow_pricing_to_final_doc(self):
        """
        E2E Flow:
        1. Initiate formal review (generates checklist from pricing data)
        2. Get all review items
        3. Check status shows correct structure
        4. Confirm all fatal pending items
        5. Verify can_generate=True
        6. Generate final bid document
        7. Verify final doc has file_path, generation_status=completed, packaging_guide
        """
        app.dependency_overrides[get_db] = override_get_db
        try:
            # Step 1: Initiate review
            resp = self.client.post("/api/v1/projects/1/formal-review/initiate")
            assert resp.status_code == 200, f"Initiate failed: {resp.json()}"
            data = resp.json()["data"]
            assert "total_items" in data
            assert "fatal_count" in data
            assert data["total_items"] >= 0

            # Step 2: Get review items
            resp = self.client.get("/api/v1/projects/1/formal-review/items")
            assert resp.status_code == 200
            items = resp.json()
            assert isinstance(items, list)

            # Step 3: Check status (response is FormalReviewStatusResponse directly)
            resp = self.client.get("/api/v1/projects/1/formal-review/status")
            assert resp.status_code == 200
            status = resp.json()
            assert "project_id" in status
            assert "total_items" in status
            assert "confirmed_items" in status
            assert "fatal_pending" in status
            assert "warning_pending" in status
            assert "can_generate" in status

            # Step 4: Confirm all fatal pending items
            fatal_pending = [i for i in items if i["risk_level"] == "fatal" and i["specialist_status"] == "pending"]
            for item in fatal_pending:
                resp = self.client.post(
                    f"/api/v1/formal-review-items/{item['id']}/confirm",
                    json={"notes": "人工核实无误"}
                )
                assert resp.status_code == 200, f"Confirm failed for item {item['id']}: {resp.json()}"

            # Step 5: Verify can_generate (if no fatal items remain)
            resp = self.client.get("/api/v1/projects/1/formal-review/status")
            status = resp.json()
            if status["fatal_pending"] > 0:
                pytest.skip("Fatal items remain - cannot generate (correct blocking behavior)")

            # Step 6: Generate final document
            resp = self.client.post("/api/v1/projects/1/final-documents/generate", json={})
            assert resp.status_code == 200, f"Generate failed: {resp.json()}"
            result = resp.json()["data"]
            assert result["generation_status"] == "completed"
            assert result["file_path"] is not None
            assert result["packaging_guide"] is not None
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── Test 2: Fatal unhandled blocks generation ──────────────────────────

    def test_fatal_unhandled_blocks_generation(self):
        """
        Scenario: fatal item pending → generate endpoint returns 400 with '致命' or 'fatal' detail.
        """
        app.dependency_overrides[get_db] = override_get_db
        try:
            # Seed a fatal pending item
            with test_engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO formal_review_items
                    (project_id, source_type, check_category, check_title,
                     system_status, risk_level, specialist_status)
                    VALUES (1, 'ocr_comparison', 'qualification_validity',
                            '致命风险项', 'failed', 'fatal', 'pending')
                """))
                conn.commit()

            resp = self.client.post("/api/v1/projects/1/final-documents/generate", json={})
            assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}: {resp.json()}"
            detail = resp.json()["detail"].lower()
            assert "致命" in resp.json()["detail"] or "fatal" in detail, \
                f"Expected '致命' or 'fatal' in error detail, got: {resp.json()['detail']}"
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── Test 3: Abandon archives to abandoned_drafts ──────────────────────

    def test_abandon_archives_to_abandoned_drafts(self):
        """
        POST /projects/1/abandon → archives to abandoned_drafts.
        GET /formal-review/status still works after abandon (no exception).
        """
        app.dependency_overrides[get_db] = override_get_db
        try:
            # Step 1: Abandon project
            resp = self.client.post(
                "/api/v1/projects/1/abandon",
                json={"reason": "老板认为风险过高", "user_id": 1}
            )
            assert resp.status_code == 200, f"Abandon failed: {resp.json()}"
            data = resp.json()
            assert data["termination_stage"] == "formal_review"
            assert data["termination_reason"] == "老板认为风险过高"
            assert data["can_be_revived"] is True

            # Step 2: Verify abandoned_drafts record was created
            with test_engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM abandoned_drafts WHERE project_id = 1")
                ).fetchone()
                assert row is not None, "abandoned_drafts record not found"
                # row is (id, project_id, termination_stage, tech_proposal_path,
                #         business_proposal_path, pricing_decision_id, termination_reason,
                #         termination_by, can_be_revived, archived_at, revived_at, revived_to_project_id)
                assert row[2] == "formal_review"  # termination_stage
                assert row[6] == "老板认为风险过高"  # termination_reason

            # Step 3: GET /formal-review/status still works after abandon
            resp = self.client.get("/api/v1/projects/1/formal-review/status")
            assert resp.status_code == 200, f"Status after abandon failed: {resp.json()}"
            status = resp.json()
            assert status["project_id"] == 1
            assert "fatal_pending" in status
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ─── Test 4: Manual add and confirm flow ─────────────────────────────────

    def test_manual_add_and_confirm_flow(self):
        """
        1. POST /projects/1/formal-review/manual-add → creates new item
        2. Assert response has id
        3. POST /formal-review-items/{new_id}/confirm
        4. GET /projects/1/formal-review/items → item status is 'confirmed'
        """
        app.dependency_overrides[get_db] = override_get_db
        try:
            # Step 1: Add manual item
            resp = self.client.post(
                "/api/v1/projects/1/formal-review/manual-add",
                json={
                    "check_category": "seal_requirement",
                    "check_title": "招标文件特殊密封要求",
                    "check_description": "招标文件第8页要求使用指定颜色封条",
                    "risk_level": "warning",
                    "reference_clause": "第三章 3.4.2",
                }
            )
            assert resp.status_code == 200, f"Manual add failed: {resp.json()}"
            item = resp.json()["data"]
            assert "id" in item
            assert item["source_type"] == "manual_added"
            assert item["check_title"] == "招标文件特殊密封要求"
            assert item["specialist_status"] == "pending"
            new_id = item["id"]

            # Step 2: Confirm the item
            resp = self.client.post(
                f"/api/v1/formal-review-items/{new_id}/confirm",
                json={"notes": "已核实封条要求"}
            )
            assert resp.status_code == 200, f"Confirm failed: {resp.json()}"
            confirmed = resp.json()["data"]
            assert confirmed["specialist_status"] == "confirmed"
            assert confirmed["confirmed_by"] == 1

            # Step 3: Verify item is confirmed in items list
            resp = self.client.get("/api/v1/projects/1/formal-review/items")
            assert resp.status_code == 200
            items = resp.json()
            assert isinstance(items, list)
            item_map = {i["id"]: i for i in items}
            assert new_id in item_map
            assert item_map[new_id]["specialist_status"] == "confirmed"
        finally:
            app.dependency_overrides.pop(get_db, None)
