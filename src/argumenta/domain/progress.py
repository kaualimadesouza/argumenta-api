"""What the Progresso screen shows: score series per dimension and milestones."""

import enum
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from argumenta.domain.enums import Dimension

WEEK_WITHOUT_MISSING_DAYS = 7


class Milestone(enum.StrEnum):
    """Derived from state, never persisted: a milestone is a question about the
    student's history, so it cannot go stale."""

    TUTORIAL_COMPLETED = "tutorial_completed"
    FIRST_REPERTOIRE_PRAISE = "first_repertoire_praise"
    FIRST_BOSS_ESSAY = "first_boss_essay"
    WEEK_WITHOUT_MISSING = "week_without_missing"


@dataclass(frozen=True)
class DimensionSample:
    dimension: Dimension
    day: date
    score: int
    """Internal 0-100, the scale the series is drawn in."""


@dataclass(frozen=True)
class TrendPoint:
    day: date
    score: int


@dataclass(frozen=True)
class DimensionTrend:
    dimension: Dimension
    points: tuple[TrendPoint, ...]


@dataclass(frozen=True)
class MilestoneFacts:
    tutorial_completed: bool
    repertoire_praises: int
    passed_boss_chapters: int
    longest_streak_days: int


@dataclass(frozen=True)
class MilestoneStatus:
    milestone: Milestone
    done: bool


def trends(
    dimensions: Iterable[Dimension], samples: Iterable[DimensionSample]
) -> tuple[DimensionTrend, ...]:
    """One series per asked dimension, oldest point first. A dimension with no
    sample keeps its empty row: the screen has a line for it either way."""
    by_dimension: dict[Dimension, list[TrendPoint]] = {}
    for sample in samples:
        by_dimension.setdefault(sample.dimension, []).append(
            TrendPoint(day=sample.day, score=sample.score)
        )
    return tuple(
        DimensionTrend(dimension=dimension, points=tuple(by_dimension.get(dimension, ())))
        for dimension in dimensions
    )


def milestones(facts: MilestoneFacts) -> tuple[MilestoneStatus, ...]:
    done = {
        Milestone.TUTORIAL_COMPLETED: facts.tutorial_completed,
        Milestone.FIRST_REPERTOIRE_PRAISE: facts.repertoire_praises > 0,
        Milestone.FIRST_BOSS_ESSAY: facts.passed_boss_chapters > 0,
        Milestone.WEEK_WITHOUT_MISSING: facts.longest_streak_days >= WEEK_WITHOUT_MISSING_DAYS,
    }
    return tuple(
        MilestoneStatus(milestone=milestone, done=done[milestone]) for milestone in Milestone
    )
