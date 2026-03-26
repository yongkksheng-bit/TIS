"""TDD tests for CostEstimationEngine."""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.week4_pricing.cost_engine import CostEstimationEngine, CostConfidence


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

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCostEstimationEngine:
    def test_breakdown_cost_returns_all_categories(self):
        """breakdown_cost returns food/labor/logistics/management in correct proportions."""
        engine = CostEstimationEngine()
        breakdown = engine.breakdown_cost(Decimal('100000'))
        assert 'food_cost' in breakdown
        assert 'labor_cost' in breakdown
        assert 'logistics_cost' in breakdown
        assert 'management_cost' in breakdown
        # 55% + 25% + 12% + 8% = 100%
        assert breakdown['food_cost'] == Decimal('55000.00')
        assert breakdown['labor_cost'] == Decimal('25000.00')
        assert breakdown['logistics_cost'] == Decimal('12000.00')
        assert breakdown['management_cost'] == Decimal('8000.00')

    def test_breakdown_cost_quantized_to_cents(self):
        """breakdown_cost values are rounded to 2 decimal places."""
        engine = CostEstimationEngine()
        breakdown = engine.breakdown_cost(Decimal('99999'))
        # Each value must be a valid Decimal with 2 decimal places
        for key in ['food_cost', 'labor_cost', 'logistics_cost', 'management_cost']:
            val = breakdown[key]
            assert val == val.quantize(Decimal('0.01'))

    def test_estimate_from_history_returns_low_confidence_without_db(self):
        """No DB → uses budget*75% fallback, confidence=low, warning set."""
        engine = CostEstimationEngine()
        result = engine.estimate_from_history(
            project_type='food',
            region='北京',
            budget=Decimal('1000000'),
            db=None,
        )
        assert result['estimated_total'] == Decimal('750000.00')
        assert result['confidence'] == 'low'
        assert result['based_on'] == '行业经验比例（预算75%）'
        assert 'warning' in result
        assert 'breakdown' in result