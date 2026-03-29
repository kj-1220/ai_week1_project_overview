"""
helpers.py — Shared utility functions for data generation.
"""

import random
import datetime
import uuid

from config import START_DATE, END_DATE


def random_date(start, end):
    """Random date between start and end (inclusive)."""
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + datetime.timedelta(days=random.randint(0, delta))


def weighted_choice(options, weights):
    """Weighted random selection."""
    return random.choices(options, weights=weights, k=1)[0]


def month_iter(start_date, end_date):
    """Yield (year, month, first_day, last_day) for each month in range."""
    d = start_date.replace(day=1)
    while d <= end_date:
        next_month = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        last_day = min(next_month - datetime.timedelta(days=1), end_date)
        yield d.year, d.month, d, last_day
        d = next_month


def make_session_id():
    """Generate a short session ID."""
    return str(uuid.uuid4())[:8]


def clamp(value, lo, hi):
    """Clamp value between lo and hi."""
    return max(lo, min(hi, value))
