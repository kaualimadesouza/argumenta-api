"""Streak math over the days a student actually practiced."""

from collections.abc import Iterable
from datetime import date, timedelta

ONE_DAY = timedelta(days=1)


def current_streak(practice_days: Iterable[date], today: date) -> int:
    """Consecutive practice days ending today or yesterday: today still counts
    as pending, not as a break."""
    days = set(practice_days)
    cursor = today if today in days else today - ONE_DAY
    streak = 0
    while cursor in days:
        streak += 1
        cursor -= ONE_DAY
    return streak


def longest_streak(practice_days: Iterable[date]) -> int:
    """The record, so a streak the student broke still shows what they once did."""
    best = run = 0
    previous: date | None = None
    for day in sorted(set(practice_days)):
        run = run + 1 if previous is not None and day - previous == ONE_DAY else 1
        previous = day
        best = max(best, run)
    return best
