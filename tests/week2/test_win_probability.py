import pytest
from app.core.week2_evaluation.win_probability_calculator import WinProbabilityCalculator

def test_qual_score_below_60_returns_zero():
    """qual_score < 60 → probability = 0 (fatal risk)."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=50, time_level='normal', relationship_index=50, competition_count=1)
    assert result == 0.0

def test_expired_time_returns_zero():
    """expired time level → probability = 0 regardless of other factors."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=80, time_level='expired', relationship_index=50, competition_count=1)
    assert result == 0.0

def test_qual_score_60_is_fatal():
    """qual_score = 60 is still fatal (< 60 threshold)."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=60, time_level='urgent', relationship_index=80, competition_count=1)
    assert result == 0.0

def test_normal_scenario_returns_valid_probability():
    """Normal scenario returns weighted probability in range [0, 1]."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=80, time_level='normal', relationship_index=50, competition_count=2)
    assert 0 <= result <= 1

def test_relaxed_time_higher_probability():
    """relaxed time should give higher probability than tight time."""
    calc = WinProbabilityCalculator()
    relaxed = calc.calculate(qual_score=80, time_level='relaxed', relationship_index=50, competition_count=2)
    tight = calc.calculate(qual_score=80, time_level='tight', relationship_index=50, competition_count=2)
    assert relaxed > tight

def test_relationship_index_impacts_probability():
    """Higher relationship_index → higher probability."""
    calc = WinProbabilityCalculator()
    high_rel = calc.calculate(qual_score=80, time_level='normal', relationship_index=80, competition_count=1)
    low_rel = calc.calculate(qual_score=80, time_level='normal', relationship_index=20, competition_count=1)
    assert high_rel > low_rel

def test_competition_count_impacts_probability():
    """More competition → lower probability."""
    calc = WinProbabilityCalculator()
    no_comp = calc.calculate(qual_score=80, time_level='normal', relationship_index=50, competition_count=1)
    high_comp = calc.calculate(qual_score=80, time_level='normal', relationship_index=50, competition_count=5)
    assert no_comp > high_comp

def test_zero_competition_max_score():
    """Zero competition should give competition_score = 100."""
    calc = WinProbabilityCalculator()
    result = calc.calculate(qual_score=100, time_level='relaxed', relationship_index=100, competition_count=0)
    # qual=100*0.4 + time=100*0.2 + rel=100*0.3 + comp=100*0.1 = 100 → normalized = 1.0
    assert result == 1.0
