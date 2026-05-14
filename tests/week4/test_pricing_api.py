"""TDD tests for Week 4 pricing API endpoints."""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models.pricing import CostEstimate, PricingDecision


# ─── In-memory test DB setup ───────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

with test_engine.connect() as conn:
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
            specialist_price NUMERIC(15, 2),
            specialist_notes TEXT,
            action_type VARCHAR(30),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
    conn.execute(text(
        "INSERT INTO projects (id, project_name, project_type, status, budget_amount, relationship_flag, owner_unit, region) "
        "VALUES (1, '测试项目', 'food', 'approved_by_specialist', 1500000, 0, '某政府', '北京')"
    ))
    conn.execute(text(
        "INSERT INTO projects (id, project_name, project_type, status, budget_amount, relationship_flag, owner_unit, region) "
        "VALUES (2, '无成本项目', 'food', 'approved_by_specialist', 2000000, 0, '某企业', '上海')"
    ))
    conn.commit()


def override_get_db():
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestCostEstimateAPI:
    def test_create_cost_estimate(self):
        response = client.post(
            "/api/v1/projects/1/cost-estimates",
            json={
                "food_cost": 800000,
                "logistics_cost": 200000,
                "labor_cost": 300000,
                "management_cost": 150000,
                "estimate_reason": "基于历史项目测算",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["version_number"] == 1
        assert data["total_cost"] > 0
        assert data["is_confirmed"] is False

    def test_confirm_cost_estimate(self):
        # First create
        resp = client.post(
            "/api/v1/projects/1/cost-estimates",
            json={
                "food_cost": 100000, "logistics_cost": 20000,
                "labor_cost": 50000, "management_cost": 20000,
                "estimate_reason": "测试",
            },
        )
        estimate_id = resp.json()["data"]["id"]
        # Then confirm
        response = client.post(f"/api/v1/cost-estimates/{estimate_id}/confirm")
        assert response.status_code == 200
        assert response.json()["data"]["is_confirmed"] is True


class TestPricingCalculationAPI:
    def test_generate_scenarios_requires_confirmed_cost(self):
        """No confirmed cost → 400. Use project_id=2 which has no cost estimates."""
        response = client.post("/api/v1/projects/2/pricing-calculations")
        assert response.status_code == 400
        assert "confirmed cost" in response.json()["detail"].lower()

    def test_generate_scenarios_with_confirmed_cost(self):
        # Create and confirm cost estimate
        resp = client.post(
            "/api/v1/projects/1/cost-estimates",
            json={
                "food_cost": 800000, "logistics_cost": 200000,
                "labor_cost": 300000, "management_cost": 150000,
                "estimate_reason": "测试确认",
            },
        )
        estimate_id = resp.json()["data"]["id"]
        client.post(f"/api/v1/cost-estimates/{estimate_id}/confirm")

        response = client.post("/api/v1/projects/1/pricing-calculations")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["scenarios"]) == 3
        assert any(s["is_recommended"] for s in data["scenarios"])


class TestPricingDecisionAPI:
    def test_loss_pricing_rejected(self):
        # Setup confirmed cost
        resp = client.post(
            "/api/v1/projects/1/cost-estimates",
            json={
                "food_cost": 800000, "logistics_cost": 200000,
                "labor_cost": 300000, "management_cost": 150000,
                "estimate_reason": "测试",
            },
        )
        client.post(f"/api/v1/cost-estimates/{resp.json()['data']['id']}/confirm")

        # Submit loss pricing (final < cost * 1.01)
        response = client.post(
            "/api/v1/projects/1/pricing-decisions",
            json={
                "boss_final_price": 900000,  # less than cost 1.45M
                "boss_decision_reason": "亏损抢占市场",
            },
        )
        assert response.status_code == 400
        assert "亏损" in response.json()["detail"]

    def test_normal_pricing_success(self):
        # Setup confirmed cost
        resp = client.post(
            "/api/v1/projects/1/cost-estimates",
            json={
                "food_cost": 800000, "logistics_cost": 200000,
                "labor_cost": 300000, "management_cost": 150000,
                "estimate_reason": "测试",
            },
        )
        client.post(f"/api/v1/cost-estimates/{resp.json()['data']['id']}/confirm")

        # Submit normal pricing (within budget limit, deviation < 5%)
        response = client.post(
            "/api/v1/projects/1/pricing-decisions",
            json={
                "boss_final_price": 1500000,  # equals budget_limit, no over_limit
                "boss_decision_reason": "合理利润定价，确保中标后有充足现金流",
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["boss_final_price"] == 1500000.0
        assert data["status"] == "decided"

    def test_pricing_decisionAdvancesProjectToAwaitingReview(self):
        """After successful pricing decision, project status must advance to awaiting_review.

        This is the Week 4 → Week 5 transition. Without this update, the project
        gets stuck in pricing phase and the formal review flow cannot begin.

        Uses project_id=2 to avoid conflict with test_normal_pricing_success which
        uses project_id=1 (both start with status='approved_by_specialist').
        """
        # Setup confirmed cost
        resp = client.post(
            "/api/v1/projects/2/cost-estimates",
            json={
                "food_cost": 800000, "logistics_cost": 200000,
                "labor_cost": 300000, "management_cost": 150000,
                "estimate_reason": "测试",
            },
        )
        client.post(f"/api/v1/cost-estimates/{resp.json()['data']['id']}/confirm")

        # Submit normal pricing decision
        response = client.post(
            "/api/v1/projects/2/pricing-decisions",
            json={
                "boss_final_price": 1500000,
                "boss_decision_reason": "合理利润定价，确保中标后有充足现金流",
            },
        )
        assert response.status_code == 200

        # Verify project status advanced to awaiting_review via DB query
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        db = TestingSessionLocal()
        try:
            from app.models.project import Project
            proj = db.query(Project).get(2)
            assert proj is not None
            assert proj.status == "awaiting_review", (
                f"Expected status 'awaiting_review' after pricing decision, got '{proj.status}'"
            )
        finally:
            db.close()

    def test_pricing_dashboard(self):
        response = client.get("/api/v1/projects/1/pricing-dashboard")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "scenarios" in data
        assert "budget_limit" in data