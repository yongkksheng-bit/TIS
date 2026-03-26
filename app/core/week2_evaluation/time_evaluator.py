# app/core/week2_evaluation/time_evaluator.py
"""Time Urgency Evaluator."""
from datetime import datetime, timedelta
from typing import Optional

class TimeEvaluator:
    """
    Calculate time urgency level based on days until bid open.

    Rules:
    - expired: days < 0
    - urgent: 1-3 days
    - tight: 4-7 days
    - normal: 8-15 days
    - relaxed: > 15 days
    """

    def calculate(self, bid_open_date: datetime, current: Optional[datetime] = None) -> dict:
        if current is None:
            current = datetime.now()

        days_remaining = (bid_open_date - current).days

        if days_remaining < 0:
            level = 'expired'
            sufficient = False
        elif days_remaining <= 3:
            level = 'urgent'
            sufficient = False
        elif days_remaining <= 7:
            level = 'tight'
            sufficient = True
        elif days_remaining <= 15:
            level = 'normal'
            sufficient = True
        else:
            level = 'relaxed'
            sufficient = True

        return {
            'days_until_bid_open': days_remaining,
            'time_urgency_level': level,
            'is_time_sufficient': sufficient,
            'working_days_estimate': int(days_remaining * 0.7) if days_remaining >= 0 else 0
        }
