import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argumenta.application.accounts.ports import ExamTargetRepository
from argumenta.application.progress.ports import StatsRepository
from argumenta.application.track.ports import (
    ActivityRepository,
    ContentRepository,
    ProgressRepository,
)
from argumenta.application.track.use_cases.get_track import DAILY_SUBMISSION_LIMIT
from argumenta.domain.enums import Dimension, Exam
from argumenta.domain.evaluation import BASE_DIMENSIONS
from argumenta.domain.habit import current_streak, longest_streak
from argumenta.domain.lenses import DEFAULT_EXAM
from argumenta.domain.progress import (
    DimensionSample,
    DimensionTrend,
    MilestoneFacts,
    MilestoneStatus,
    milestones,
    trends,
)
from argumenta.domain.track import StoryState, fold_stories

TREND_WINDOW_DAYS = 30


def _shown_dimensions(samples: Sequence[DimensionSample]) -> tuple[Dimension, ...]:
    """The base five always, so the screen keeps its rows even for a student who
    never wrote, plus any extra dimension actually graded (the ENEM proposal)."""
    graded = {sample.dimension for sample in samples}
    extra = tuple(
        dimension
        for dimension in Dimension
        if dimension not in BASE_DIMENSIONS and dimension in graded
    )
    return (*BASE_DIMENSIONS, *extra)


@dataclass(frozen=True)
class ProgressView:
    exam: Exam
    streak_days: int
    longest_streak_days: int
    submissions_today: int
    daily_limit: int
    stories_completed: int
    stories_total: int
    trends: tuple[DimensionTrend, ...]
    milestones: tuple[MilestoneStatus, ...]


class GetProgressUseCase:
    """Read-only, unlike GetTrackUseCase: opening the progress screen must not
    move the student's state machine."""

    def __init__(
        self,
        content: ContentRepository,
        progress: ProgressRepository,
        activity: ActivityRepository,
        stats: StatsRepository,
        exams: ExamTargetRepository,
    ) -> None:
        self._content = content
        self._progress = progress
        self._activity = activity
        self._stats = stats
        self._exams = exams

    def execute(self, user_id: uuid.UUID) -> ProgressView:
        now = datetime.now(tz=UTC)
        practice_days = self._activity.practice_days(user_id)
        record = longest_streak(practice_days)
        samples = self._stats.dimension_history(
            user_id, since=now - timedelta(days=TREND_WINDOW_DAYS)
        )
        stories = fold_stories(
            self._content.list_published_stories(), self._progress.statuses_for_user(user_id)
        )
        completed = [item.story for item in stories if item.state == StoryState.COMPLETED]
        return ProgressView(
            exam=self._exams.active_exam(user_id) or DEFAULT_EXAM,
            streak_days=current_streak(practice_days, now.date()),
            longest_streak_days=record,
            submissions_today=self._activity.submissions_on(user_id, now.date()),
            daily_limit=DAILY_SUBMISSION_LIMIT,
            stories_completed=len(completed),
            stories_total=len(stories),
            trends=trends(_shown_dimensions(samples), samples),
            milestones=milestones(
                MilestoneFacts(
                    tutorial_completed=any(story.is_tutorial for story in completed),
                    repertoire_praises=self._stats.repertoire_praises(user_id),
                    passed_boss_chapters=self._stats.passed_boss_chapters(user_id),
                    longest_streak_days=record,
                )
            ),
        )
