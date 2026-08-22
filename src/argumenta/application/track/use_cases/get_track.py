import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from argumenta.application.track.ports import (
    ActivityRepository,
    ContentRepository,
    ProgressRepository,
)
from argumenta.domain.enums import ChapterStatus
from argumenta.domain.habit import current_streak
from argumenta.domain.track import StoryProgress, fold_stories, next_playable_chapter

DAILY_SUBMISSION_LIMIT = 3


@dataclass(frozen=True)
class TrackView:
    stories: tuple[StoryProgress, ...]
    streak_days: int
    submissions_today: int
    daily_limit: int


class GetTrackUseCase:
    def __init__(
        self,
        content: ContentRepository,
        progress: ProgressRepository,
        activity: ActivityRepository,
    ) -> None:
        self._content = content
        self._progress = progress
        self._activity = activity

    def execute(self, user_id: uuid.UUID) -> TrackView:
        stories = self._content.list_published_stories()
        statuses = self._progress.statuses_for_user(user_id)

        # reading the track materializes the next unlock: first chapter of the
        # track for a new user, or the chapter after the last passed one
        now = datetime.now(tz=UTC)
        playable = next_playable_chapter(stories, statuses)
        if playable is not None:
            self._progress.unlock(user_id, playable, at=now)
            statuses[playable] = ChapterStatus.AVAILABLE

        return TrackView(
            stories=fold_stories(stories, statuses),
            streak_days=current_streak(self._activity.practice_days(user_id), now.date()),
            submissions_today=self._activity.submissions_on(user_id, now.date()),
            daily_limit=DAILY_SUBMISSION_LIMIT,
        )
