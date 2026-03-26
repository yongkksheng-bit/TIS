# app/core/week2_evaluation/win_probability_calculator.py
"""Win Probability Calculator - Heuristic Algorithm.

Per Master Spec §8.2:
- Weights: qualification 40% + time 20% + relationship 30% + competition 10%
- Fatal risk: qual_score < 60 OR time_level == 'expired' → probability = 0
"""
from typing import Optional

class WinProbabilityCalculator:
    """
    Calculate comprehensive win probability using heuristic algorithm.

    Formula (per Master Spec):
    base = (qual_score*0.4 + time_score*0.2 + relationship_index*0.3 + competition_score*0.1) / 100
    Fatal: qual_score < 60 OR expired → 0
    """

    TIME_SCORES = {
        'expired': 0,
        'urgent': 40,
        'tight': 60,
        'normal': 80,
        'relaxed': 100
    }

    def calculate(
        self,
        qual_score: int,
        time_level: str,
        relationship_index: int,
        competition_count: int = 1
    ) -> float:
        """Calculate win probability 0-1."""
        # Fatal risk override - one vote veto (qual_score < 60 per Master Spec §8.2)
        if qual_score < 60:
            return 0.0
        if time_level == 'expired':
            return 0.0

        time_score = self.TIME_SCORES.get(time_level, 0)
        competition_score = max(0, 100 - competition_count * 10)

        base = (
            qual_score * 0.4 +
            time_score * 0.2 +
            relationship_index * 0.3 +
            competition_score * 0.1
        ) / 100

        return min(max(base, 0.0), 1.0)
