from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from argumenta.application.accounts.ports import ExamTargetRepository
from argumenta.application.progress.ports import StatsRepository
from argumenta.application.progress.use_cases import GetProgressUseCase
from argumenta.application.track.ports import (
    ActivityRepository,
    ContentRepository,
    ProgressRepository,
)
from argumenta.domain.enums import Dimension, Exam
from argumenta.domain.lenses import LENS_VERSION, criterion_for
from argumenta.domain.progress import DimensionTrend, Milestone
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_activity_repository,
    get_content_repository,
    get_exam_target_repository,
    get_progress_repository,
    get_stats_repository,
)

router = APIRouter(tags=["progress"])

Content = Annotated[ContentRepository, Depends(get_content_repository)]
Progress = Annotated[ProgressRepository, Depends(get_progress_repository)]
Activity = Annotated[ActivityRepository, Depends(get_activity_repository)]
Stats = Annotated[StatsRepository, Depends(get_stats_repository)]
Targets = Annotated[ExamTargetRepository, Depends(get_exam_target_repository)]


class TrendPointResponse(BaseModel):
    day: date
    score: int


class DimensionTrendResponse(BaseModel):
    dimension: Dimension
    criterion_code: str | None
    criterion_label: str | None
    """How the student's lens names this dimension; null when it hides it."""
    points: list[TrendPointResponse]


class MilestoneResponse(BaseModel):
    code: Milestone
    done: bool


class ProgressResponse(BaseModel):
    """The Progresso screen in one call: habit, series per dimension, milestones."""

    exam: Exam
    lens_version: str
    streak_days: int
    longest_streak_days: int
    submissions_today: int
    daily_limit: int
    stories_completed: int
    stories_total: int
    dimensions: list[DimensionTrendResponse]
    milestones: list[MilestoneResponse]


def _trend(trend: DimensionTrend, exam: Exam) -> DimensionTrendResponse:
    criterion = criterion_for(exam, trend.dimension)
    return DimensionTrendResponse(
        dimension=trend.dimension,
        criterion_code=criterion.code if criterion else None,
        criterion_label=criterion.label if criterion else None,
        points=[TrendPointResponse(day=point.day, score=point.score) for point in trend.points],
    )


@router.get("/progress")
def get_progress(
    user_id: CurrentUserId,
    content: Content,
    progress: Progress,
    activity: Activity,
    stats: Stats,
    targets: Targets,
) -> ProgressResponse:
    view = GetProgressUseCase(content, progress, activity, stats, targets).execute(user_id)
    return ProgressResponse(
        exam=view.exam,
        lens_version=LENS_VERSION,
        streak_days=view.streak_days,
        longest_streak_days=view.longest_streak_days,
        submissions_today=view.submissions_today,
        daily_limit=view.daily_limit,
        stories_completed=view.stories_completed,
        stories_total=view.stories_total,
        dimensions=[_trend(item, view.exam) for item in view.trends],
        milestones=[
            MilestoneResponse(code=status.milestone, done=status.done) for status in view.milestones
        ],
    )
