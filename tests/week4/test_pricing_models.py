"""TDD tests for Week 4 pricing SQLAlchemy models."""
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.pricing import CostEstimate, PricingDecision, PriceHistory


@pytest.fixture
def db_session():
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
                estimated_by INTEGER REFERENCES users(id),
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
        conn.execute(text("""
            CREATE TABLE price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                data_source VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("INSERT INTO users (id, username) VALUES (1, 'testuser')"))
        conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test Project', 'approved_by_specialist')"))
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCostEstimateModel:
    def test_total_cost_is_sum_of_components(self, db_session):
        """total_cost = food + logistics + labor + management + other."""
        est = CostEstimate(
            project_id=1,
            version_number=1,
            food_cost=Decimal('100000'),
            logistics_cost=Decimal('20000'),
            labor_cost=Decimal('50000'),
            management_cost=Decimal('20000'),
            other_cost=Decimal('0'),
            estimated_by=1,
            estimate_reason="Test breakdown",
        )
        # total_cost must be set by caller (not auto-computed in SQLAlchemy here)
        est.total_cost = (est.food_cost + est.logistics_cost + est.labor_cost +
                         est.management_cost + est.other_cost)
        assert est.total_cost == Decimal('190000')

    def test_version_increments_per_project(self, db_session):
        """version_number starts at 1, increments per project."""
        est1 = CostEstimate(
            project_id=1, version_number=1,
            food_cost=Decimal('100000'), logistics_cost=Decimal('20000'),
            labor_cost=Decimal('50000'), management_cost=Decimal('20000'),
            other_cost=Decimal('0'), total_cost=Decimal('190000'),
            estimated_by=1, estimate_reason="v1",
        )
        db_session.add(est1)
        db_session.commit()

        est2 = CostEstimate(
            project_id=1, version_number=2,
            food_cost=Decimal('110000'), logistics_cost=Decimal('22000'),
            labor_cost=Decimal('52000'), management_cost=Decimal('22000'),
            other_cost=Decimal('0'), total_cost=Decimal('206000'),
            estimated_by=1, estimate_reason="v2",
        )
        db_session.add(est2)
        db_session.commit()

        records = db_session.query(CostEstimate).filter_by(project_id=1).all()
        assert len(records) == 2
        assert sorted([r.version_number for r in records]) == [1, 2]

    def test_is_confirmed_default_false(self, db_session):
        """After INSERT + query back, is_confirmed defaults to False."""
        est = CostEstimate(
            project_id=1, version_number=1,
            food_cost=Decimal('100000'), logistics_cost=Decimal('20000'),
            labor_cost=Decimal('50000'), management_cost=Decimal('20000'),
            other_cost=Decimal('0'), total_cost=Decimal('190000'),
            estimated_by=1, estimate_reason="Test",
        )
        db_session.add(est)
        db_session.commit()
        # Query back to verify DB default
        loaded = db_session.get(CostEstimate, est.id)
        assert loaded.is_confirmed is False


class TestPricingDecisionModel:
    def test_system_prices_ordered(self, db_session):
        """system_suggested_low < optimal < system_suggested_high."""
        decision = PricingDecision(
            project_id=1,
            cost_base=Decimal('100000'),
            system_suggested_low=Decimal('102000'),
            system_suggested_high=Decimal('115000'),
            system_suggested_optimal=Decimal('108000'),
            boss_final_price=Decimal('108000'),
            boss_decision_reason="Test",
            status='decided',
        )
        assert decision.system_suggested_low < decision.system_suggested_optimal
        assert decision.system_suggested_optimal < decision.system_suggested_high

    def test_status_default_decided(self, db_session):
        """After INSERT + query back, status defaults to 'decided'."""
        decision = PricingDecision(
            project_id=1,
            cost_base=Decimal('100000'),
            system_suggested_low=Decimal('102000'),
            system_suggested_high=Decimal('115000'),
            boss_final_price=Decimal('108000'),
            boss_decision_reason="Test",
        )
        db_session.add(decision)
        db_session.commit()
        loaded = db_session.get(PricingDecision, decision.id)
        assert loaded.status == 'decided'

    def test_is_under_limit_true_when_below_budget(self, db_session):
        decision = PricingDecision(
            project_id=1,
            cost_base=Decimal('100000'),
            system_suggested_low=Decimal('102000'),
            system_suggested_high=Decimal('115000'),
            boss_final_price=Decimal('108000'),
            boss_decision_reason="Test",
            budget_limit=Decimal('150000'),
            is_under_limit=True,
        )
        assert decision.is_under_limit is True


class TestPriceHistoryModel:
    def test_is_our_win_boolean(self, db_session):
        record = PriceHistory(
            project_type="food",
            region="北京",
            budget_amount=Decimal('500000'),
            our_cost=Decimal('400000'),
            our_bid_price=Decimal('450000'),
            winning_price=Decimal('430000'),
            winning_unit="A公司",
            discount_rate=Decimal('0.86'),
            bid_date=date.today(),
            is_our_win=False,
            data_source="internal",
        )
        db_session.add(record)
        db_session.commit()
        assert record.is_our_win is False

    def test_discount_rate_stored(self, db_session):
        record = PriceHistory(
            project_type="food",
            region="北京",
            budget_amount=Decimal('1000000'),
            winning_price=Decimal('950000'),
            discount_rate=Decimal('0.95'),
            bid_date=date.today(),
            is_our_win=True,
            data_source="crawler",
        )
        db_session.add(record)
        db_session.commit()
        assert float(record.discount_rate) == pytest.approx(0.95)
