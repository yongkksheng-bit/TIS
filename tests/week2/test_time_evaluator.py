import pytest
from datetime import datetime, timedelta
from app.core.week2_evaluation.time_evaluator import TimeEvaluator

def test_expired_bid_open():
    """Bid open date in past → 'expired'."""
    evaluator = TimeEvaluator()
    past = datetime.now() - timedelta(days=1)
    result = evaluator.calculate(past)
    assert result['time_urgency_level'] == 'expired'
    assert result['is_time_sufficient'] is False

def test_urgent_3_days():
    """1-3 days remaining → 'urgent'."""
    evaluator = TimeEvaluator()
    soon = datetime.now() + timedelta(days=2)
    result = evaluator.calculate(soon)
    assert result['time_urgency_level'] == 'urgent'
    assert result['is_time_sufficient'] is False

def test_tight_5_days():
    """4-7 days → 'tight'."""
    evaluator = TimeEvaluator()
    soon = datetime.now() + timedelta(days=5)
    result = evaluator.calculate(soon)
    assert result['time_urgency_level'] == 'tight'
    assert result['is_time_sufficient'] is True

def test_normal_10_days():
    """8-15 days → 'normal'."""
    evaluator = TimeEvaluator()
    future = datetime.now() + timedelta(days=10)
    result = evaluator.calculate(future)
    assert result['time_urgency_level'] == 'normal'
    assert result['is_time_sufficient'] is True

def test_relaxed_20_days():
    """>15 days → 'relaxed'."""
    evaluator = TimeEvaluator()
    future = datetime.now() + timedelta(days=20)
    result = evaluator.calculate(future)
    assert result['time_urgency_level'] == 'relaxed'
    assert result['is_time_sufficient'] is True

def test_days_until_bid_open():
    """Verify exact days_remaining calculation."""
    evaluator = TimeEvaluator()
    future = datetime.now() + timedelta(days=7)
    result = evaluator.calculate(future)
    assert result['days_until_bid_open'] == 7
