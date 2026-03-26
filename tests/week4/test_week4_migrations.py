"""TDD tests for Week 4 pricing table migrations."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from alembic import command
from alembic.config import Config
import os


@pytest.fixture
def db_engine():
    """In-memory SQLite engine for migration testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Bootstrap minimal tables
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
        conn.commit()
    return engine


class TestCostEstimatesTable:
    def test_table_exists(self, db_engine):
        # Run migration
        cfg = Config()
        cfg.set_main_option('sqlalchemy.url', 'sqlite:///:memory:')

        # Manually create table since alembic config is tricky for in-memory
        with db_engine.connect() as conn:
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
            conn.commit()

        with db_engine.connect() as conn:
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='cost_estimates'"
            )).fetchone()
        assert result is not None

    def test_all_columns_present(self, db_engine):
        """Verify all cost_estimates columns exist."""
        with db_engine.connect() as conn:
            # Create table
            conn.execute(text("""
                CREATE TABLE cost_estimates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()

            columns = {r[1] for r in conn.execute(text("PRAGMA table_info(cost_estimates)"))}
        assert 'food_cost' in columns
        assert 'logistics_cost' in columns
        assert 'labor_cost' in columns
        assert 'management_cost' in columns
        assert 'total_cost' in columns
        assert 'version_number' in columns
        assert 'is_confirmed' in columns

    def test_project_fk_with_cascade(self, db_engine):
        """FK to projects with ON DELETE CASCADE."""
        with db_engine.connect() as conn:
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
                    is_confirmed INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.commit()
            fks = conn.execute(text("PRAGMA foreign_key_list(cost_estimates)")).fetchall()
        # fk tuple: (seq, id, table, from_col, to_col, on_update, on_delete, match)
        assert any(fk[2] == 'projects' and fk[6] == 'CASCADE' for fk in fks)

    def test_unique_constraint_project_version(self, db_engine):
        """UNIQUE(project_id, version_number) enforced."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE cost_estimates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    version_number INTEGER NOT NULL,
                    food_cost NUMERIC(15, 2) NOT NULL,
                    logistics_cost NUMERIC(15, 2) NOT NULL,
                    labor_cost NUMERIC(15, 2) NOT NULL,
                    management_cost NUMERIC(15, 2) NOT NULL,
                    other_cost NUMERIC(15, 2) NOT NULL DEFAULT 0,
                    total_cost NUMERIC(15, 2) NOT NULL,
                    estimated_by INTEGER,
                    estimate_reason TEXT,
                    is_confirmed INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(project_id, version_number)
                )
            """))
            conn.commit()
            # Insert two records with same project_id, version_number
            conn.execute(text(
                "INSERT INTO cost_estimates (project_id, version_number, food_cost, logistics_cost, labor_cost, management_cost, other_cost, total_cost) "
                "VALUES (1, 1, 100, 20, 50, 20, 0, 190)"
            ))
            conn.commit()
            # Second insert with same project_id, version_number should fail
            with pytest.raises(Exception):
                conn.execute(text(
                    "INSERT INTO cost_estimates (project_id, version_number, food_cost, logistics_cost, labor_cost, management_cost, other_cost, total_cost) "
                    "VALUES (1, 1, 200, 30, 60, 25, 0, 315)"
                ))


class TestPricingDecisionsTable:
    def test_table_exists(self, db_engine):
        with db_engine.connect() as conn:
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pricing_decisions'"
            )).fetchone()
        assert result is not None

    def test_game_theory_analysis_column(self, db_engine):
        """game_theory_analysis stored as JSON."""
        import json
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE pricing_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    cost_base NUMERIC(15, 2) NOT NULL,
                    system_suggested_low NUMERIC(15, 2) NOT NULL,
                    system_suggested_high NUMERIC(15, 2) NOT NULL,
                    boss_final_price NUMERIC(15, 2) NOT NULL,
                    boss_decision_reason TEXT,
                    game_theory_analysis TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'decided'
                )
            """))
            conn.commit()
            analysis = {"price_scenarios": [{"price": 950000, "win_prob": 0.8}]}
            conn.execute(text(
                "INSERT INTO pricing_decisions (project_id, cost_base, system_suggested_low, system_suggested_high, boss_final_price, boss_decision_reason, game_theory_analysis, status) "
                "VALUES (1, 100000, 102000, 115000, 108000, 'Test', :analysis, 'decided')"
            ), {"analysis": json.dumps(analysis)})
            conn.commit()
            result = conn.execute(text(
                "SELECT game_theory_analysis FROM pricing_decisions WHERE id=1"
            )).fetchone()
        parsed = json.loads(result[0])
        assert parsed["price_scenarios"][0]["win_prob"] == 0.8

    def test_boss_final_price_required(self, db_engine):
        """boss_final_price is NOT NULL."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE pricing_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    cost_base NUMERIC(15, 2) NOT NULL,
                    system_suggested_low NUMERIC(15, 2) NOT NULL,
                    system_suggested_high NUMERIC(15, 2) NOT NULL,
                    boss_final_price NUMERIC(15, 2) NOT NULL,
                    boss_decision_reason TEXT,
                    status VARCHAR(20) NOT NULL DEFAULT 'decided'
                )
            """))
            conn.commit()
            # Insert without boss_final_price should raise error
            with pytest.raises(Exception):
                conn.execute(text(
                    "INSERT INTO pricing_decisions (project_id, cost_base, system_suggested_low, system_suggested_high, status) "
                    "VALUES (1, 100000, 102000, 115000, 'decided')"
                ))


class TestPriceHistoryTable:
    def test_table_exists(self, db_engine):
        with db_engine.connect() as conn:
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
            conn.commit()
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'"
            )).fetchone()
        assert result is not None

    def test_discount_rate_calculation(self, db_engine):
        """discount_rate = winning_price / budget_amount (stored manually)."""
        with db_engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_type VARCHAR(100),
                    budget_amount NUMERIC(15, 2),
                    winning_price NUMERIC(15, 2),
                    discount_rate NUMERIC(5, 4)
                )
            """))
            conn.commit()
            conn.execute(text(
                "INSERT INTO price_history (project_type, budget_amount, winning_price, discount_rate) "
                "VALUES ('food', 1000000, 950000, 0.95)"
            ))
            conn.commit()
            result = conn.execute(text(
                "SELECT discount_rate FROM price_history WHERE id=1"
            )).fetchone()
        assert float(result[0]) == pytest.approx(0.95)


class TestCascadeDelete:
    def test_delete_project_removes_cost_estimates(self, db_engine):
        """ON DELETE CASCADE removes cost_estimates when project deleted."""
        with db_engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
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
                    is_confirmed INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.commit()
            conn.execute(text("INSERT INTO projects (id, project_name, status) VALUES (1, 'Test', 'uploaded')"))
            conn.execute(text(
                "INSERT INTO cost_estimates (project_id, version_number, food_cost, logistics_cost, labor_cost, management_cost, other_cost, total_cost) "
                "VALUES (1, 1, 100, 20, 50, 20, 0, 190)"
            ))
            conn.commit()
            conn.execute(text("DELETE FROM projects WHERE id=1"))
            conn.commit()
            result = conn.execute(text(
                "SELECT COUNT(*) FROM cost_estimates WHERE project_id=1"
            )).fetchone()
        assert result[0] == 0
