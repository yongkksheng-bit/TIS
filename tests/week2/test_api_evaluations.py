"""TDD Tests for Evaluation API Endpoints - Week 2 Task 7."""
import pytest
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db

# Test database setup - use StaticPool to reuse the same connection for in-memory SQLite
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

# Create all tables using raw SQL
with test_engine.connect() as conn:
    # Create users table
    conn.execute(text("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create standard_certifications table
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
    # Create tender_documents table
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
    # Create bid_documents table
    conn.execute(text("""
        CREATE TABLE bid_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            doc_type VARCHAR(50) NOT NULL,
            file_path VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create document_images table
    conn.execute(text("""
        CREATE TABLE document_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES bid_documents(id) ON DELETE CASCADE,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            image_path VARCHAR(500),
            page_number INTEGER,
            image_hash VARCHAR(64),
            image_type VARCHAR(50) NOT NULL DEFAULT 'other',
            ocr_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create ocr_extractions table
    conn.execute(text("""
        CREATE TABLE ocr_extractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL REFERENCES document_images(id) ON DELETE CASCADE,
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
    # Create owner_profiles table
    conn.execute(text("""
        CREATE TABLE owner_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_name VARCHAR(255) NOT NULL,
            owner_type VARCHAR(50),
            region VARCHAR(100),
            cooperation_count INTEGER DEFAULT 0,
            last_cooperation_date DATE,
            relationship_level VARCHAR(20) DEFAULT 'none',
            avg_winning_discount NUMERIC(5, 2),
            preferred_styles TEXT,
            common_requirements TEXT,
            blacklist_flags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_name, region)
        )
    """))
    # Create bid_evaluation_reports table
    conn.execute(text("""
        CREATE TABLE bid_evaluation_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            report_version INTEGER DEFAULT 1,
            qualification_match_score INTEGER,
            missing_mandatory_certs TEXT,
            missing_optional_certs TEXT,
            matched_certs_detail TEXT,
            days_until_bid_open INTEGER,
            time_urgency_level VARCHAR(20),
            is_time_sufficient INTEGER,
            owner_profile_id INTEGER REFERENCES owner_profiles(id),
            relationship_index INTEGER,
            is_new_owner INTEGER,
            estimated_cost NUMERIC(15, 2),
            suggested_price_range_low NUMERIC(15, 2),
            suggested_price_range_high NUMERIC(15, 2),
            cost_estimate_confidence VARCHAR(20),
            overall_win_probability NUMERIC(5, 4),
            risk_level VARCHAR(20),
            fatal_risks TEXT,
            warning_risks TEXT,
            recommendation VARCHAR(20),
            recommendation_reason VARCHAR(500),
            generated_by VARCHAR(50) DEFAULT 'system',
            confirmed_by_specialist INTEGER DEFAULT 0,
            specialist_decision VARCHAR(20),
            specialist_notes VARCHAR(500),
            confirmed_at TIMESTAMP,
            overridden_by_boss INTEGER DEFAULT 0,
            boss_override_reason VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, report_version),
            CHECK (qualification_match_score BETWEEN 0 AND 100),
            CHECK (relationship_index BETWEEN 0 AND 100)
        )
    """))
    # Create approval_logs table
    conn.execute(text("""
        CREATE TABLE approval_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id),
            action_type VARCHAR(50) NOT NULL,
            actor_role VARCHAR(50) NOT NULL,
            actor_id INTEGER REFERENCES users(id),
            reason_text TEXT,
            original_status VARCHAR(50),
            new_status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    # Create discarded_projects table
    conn.execute(text("""
        CREATE TABLE discarded_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id),
            original_evaluation_report_id INTEGER REFERENCES bid_evaluation_reports(id),
            discarded_by VARCHAR(50) NOT NULL,
            discard_reason TEXT,
            discard_stage VARCHAR(50),
            can_be_revived INTEGER DEFAULT 1,
            revived_at TIMESTAMP,
            revived_by INTEGER REFERENCES users(id),
            revived_to_project_id INTEGER REFERENCES projects(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.commit()


def override_get_db():
    """Override get_db dependency for testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply the dependency override
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture
def seed_test_data():
    """Seed minimal test data for API tests."""
    with test_engine.connect() as conn:
        # Create users
        conn.execute(text("""
            INSERT INTO users (id, username, email) VALUES (1, 'specialist', 'specialist@test.com')
        """))
        conn.execute(text("""
            INSERT INTO users (id, username, email) VALUES (2, 'boss', 'boss@test.com')
        """))

        # Create project with bid_open_date = today + 30 days
        bid_date = datetime.now() + timedelta(days=30)
        conn.execute(text("""
            INSERT INTO projects (id, project_name, project_type, bid_open_date, status, created_by, owner_unit, region)
            VALUES (1, 'Test Project', 'food', :bid_date, 'evaluation_ready', 1, 'Test Owner', 'Beijing')
        """), {"bid_date": bid_date})

        conn.commit()
    yield
    # Cleanup
    with test_engine.connect() as conn:
        conn.execute(text("DELETE FROM bid_evaluation_reports"))
        conn.execute(text("DELETE FROM discarded_projects"))
        conn.execute(text("DELETE FROM approval_logs"))
        conn.execute(text("DELETE FROM projects"))
        conn.execute(text("DELETE FROM users"))
        conn.commit()


@pytest.fixture
def seed_project_with_report(seed_test_data):
    """Create a project with bid_evaluation_report for approval tests."""
    with test_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO bid_evaluation_reports (
                id, project_id, report_version, qualification_match_score,
                missing_mandatory_certs, fatal_risks, time_urgency_level,
                recommendation, confirmed_by_specialist
            )
            VALUES (
                1, 1, 1, 85,
                '[]', '[]', 'relaxed',
                'worth_bidding', 0
            )
        """))
        conn.commit()
    yield
    # Cleanup
    with test_engine.connect() as conn:
        conn.execute(text("DELETE FROM bid_evaluation_reports WHERE project_id = 1"))
        conn.execute(text("UPDATE projects SET status = 'evaluation_ready' WHERE id = 1"))
        conn.execute(text("UPDATE projects SET generation_mode = NULL WHERE id = 1"))
        conn.execute(text("DELETE FROM approval_logs WHERE project_id = 1"))
        conn.commit()


class TestGenerateEvaluationReport:
    """Tests for POST /api/v1/projects/{project_id}/evaluations/generate"""

    def test_generate_evaluation_report(self, seed_test_data):
        """POST to generate, verify 200 with data."""
        response = client.post(
            "/api/v1/projects/1/evaluations/generate",
            json={
                "estimated_staff_count": 50,
                "service_months": 12,
                "required_deposit": 10000.0,
                "has_special_requirements": False
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["message"] == "success"
        assert "data" in data
        assert "report_id" in data["data"]
        assert "qualification" in data["data"]
        assert "time" in data["data"]
        assert "owner" in data["data"]
        assert "cost" in data["data"]
        assert "probability" in data["data"]
        assert "recommendation" in data["data"]
        assert "risks" in data["data"]

    def test_generate_report_project_not_found(self):
        """Invalid project_id -> 400/404."""
        response = client.post(
            "/api/v1/projects/99999/evaluations/generate",
            json={}
        )
        assert response.status_code == 400

    def test_generate_report_no_user_inputs(self, seed_test_data):
        """Generate report without user inputs should still work."""
        response = client.post(
            "/api/v1/projects/1/evaluations/generate"
        )
        assert response.status_code == 200


class TestGetLatestEvaluation:
    """Tests for GET /api/v1/projects/{project_id}/evaluations/latest"""

    def test_get_latest_evaluation_found(self, seed_test_data):
        """GET latest, verify 200 with report data."""
        # First generate a report
        client.post("/api/v1/projects/1/evaluations/generate", json={})

        # Then get latest
        response = client.get("/api/v1/projects/1/evaluations/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data

    def test_get_latest_evaluation_not_found(self, seed_test_data):
        """No report -> 404."""
        response = client.get("/api/v1/projects/1/evaluations/latest")
        assert response.status_code == 404


class TestSpecialistApprove:
    """Tests for POST /api/v1/evaluations/{report_id}/approve"""

    def test_specialist_approve_success(self, seed_project_with_report):
        """POST approve with AUTO mode -> 200."""
        response = client.post(
            "/api/v1/evaluations/1/approve",
            json={
                "action": "approve",
                "generation_mode": "AUTO",
                "user_id": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_specialist_approve_requires_generation_mode(self, seed_project_with_report):
        """generation_mode is required."""
        response = client.post(
            "/api/v1/evaluations/1/approve",
            json={
                "action": "approve",
                "user_id": 1
            }
        )
        assert response.status_code == 422  # Validation error

    def test_specialist_approve_fatal_risks_requires_reason(self):
        """Approve with fatal risks without reason -> 400."""
        # Create project with fatal risks
        with test_engine.connect() as conn:
            bid_date = datetime.now() + timedelta(days=30)
            conn.execute(text("""
                INSERT INTO projects (id, project_name, project_type, bid_open_date, status, created_by, owner_unit, region)
                VALUES (2, 'Risky Project', 'food', :bid_date, 'evaluation_ready', 1, 'Risky Owner', 'Beijing')
            """), {"bid_date": bid_date})

            conn.execute(text("""
                INSERT INTO bid_evaluation_reports (
                    id, project_id, report_version, qualification_match_score,
                    missing_mandatory_certs, fatal_risks, time_urgency_level,
                    recommendation, confirmed_by_specialist
                )
                VALUES (
                    2, 2, 1, 85,
                    '[]', '["Missing mandatory certificate: FOOD-BUSINESS-LICENSE"]',
                    'relaxed', 'abandon', 0
                )
            """))
            conn.commit()

        response = client.post(
            "/api/v1/evaluations/2/approve",
            json={
                "action": "approve",
                "generation_mode": "AUTO",
                "user_id": 1
            }
        )
        assert response.status_code == 400
        assert "override_reason" in response.json()["detail"].lower() or "10 characters" in response.json()["detail"].lower()

        # Cleanup
        with test_engine.connect() as conn:
            conn.execute(text("DELETE FROM bid_evaluation_reports WHERE project_id = 2"))
            conn.execute(text("DELETE FROM projects WHERE id = 2"))
            conn.commit()


class TestBossOverride:
    """Tests for POST /api/v1/evaluations/{report_id}/override"""

    @pytest.fixture
    def seed_approved_project(self, seed_project_with_report):
        """A project that has been approved by specialist."""
        # First specialist approves
        client.post(
            "/api/v1/evaluations/1/approve",
            json={
                "action": "approve",
                "generation_mode": "AUTO",
                "user_id": 1
            }
        )
        yield
        # Cleanup
        with test_engine.connect() as conn:
            conn.execute(text("DELETE FROM discarded_projects WHERE project_id = 1"))
            conn.execute(text("UPDATE projects SET status = 'evaluation_ready' WHERE id = 1"))
            conn.execute(text("UPDATE projects SET generation_mode = NULL WHERE id = 1"))
            conn.execute(text("UPDATE bid_evaluation_reports SET overridden_by_boss = 0, boss_override_reason = NULL WHERE project_id = 1"))
            conn.execute(text("DELETE FROM approval_logs WHERE project_id = 1"))
            conn.commit()

    def test_boss_override_terminate_success(self, seed_approved_project):
        """POST override_terminate -> 200."""
        response = client.post(
            "/api/v1/evaluations/1/override",
            json={
                "new_action": "override_terminate",
                "new_mode": "GUIDED",
                "reason": "Budget constraints - cannot proceed",
                "user_id": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_boss_override_requires_reason(self, seed_approved_project):
        """Override without reason -> 400."""
        response = client.post(
            "/api/v1/evaluations/1/override",
            json={
                "new_action": "override_terminate",
                "new_mode": "GUIDED",
                "user_id": 2
            }
        )
        assert response.status_code == 422  # Validation error - reason is required


class TestResponseWrapperFormat:
    """Tests for ResponseWrapper format verification."""

    def test_response_wrapper_format(self, seed_test_data):
        """Verify all responses wrapped in ResponseWrapper."""
        # Generate a report
        response = client.post(
            "/api/v1/projects/1/evaluations/generate",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        # Verify ResponseWrapper format
        assert "code" in data
        assert "message" in data
        assert "data" in data
        assert data["code"] == 200
        assert data["message"] == "success"
