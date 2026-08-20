import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from argumenta.application.track.ports import (
    ActivityRepository,
    ContentRepository,
    ProgressRepository,
)
from argumenta.domain.enums import ChapterStatus
from argumenta.domain.track import (
    StoryState,
    StorySummary,
    derive_story_state,
    next_playable_chapter,
)

DAILY_SUBMISSION_LIMIT = 3


@dataclass(frozen=True)
class TrackStory:
    story: StorySummary
    state: StoryState
    chapters_passed: int
    chapters_total: int


@dataclass(frozen=True)
class TrackView:
    stories: list[TrackStory]
    streak_days: int
    submissions_today: int
    daily_limit: int


def _current_streak(practice_days: list[date], today: date) -> int:
    """Consecutive practice days ending today or yesterday (today still counts
    as pending, not as a break)."""
    streak = 0
    days = set(practice_days)
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


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
        playable = next_playable_chapter(stories, statuses)
        if playable is not None:
            now = datetime.now(tz=UTC)
            self._progress.unlock(user_id, playable, at=now)
            statuses[playable] = ChapterStatus.AVAILABLE

        track: list[TrackStory] = []
        previous_completed = True
        for story in stories:
            state = derive_story_state(story.chapter_ids, statuses, previous_completed)
            passed = sum(
                1
                for chapter_id in story.chapter_ids
                if statuses.get(chapter_id) == ChapterStatus.PASSED
            )
            track.append(
                TrackStory(
                    story=story,
                    state=state,
                    chapters_passed=passed,
                    chapters_total=len(story.chapter_ids),
                )
            )
            previous_completed = state == StoryState.COMPLETED

        today = datetime.now(tz=UTC).date()
        return TrackView(
            stories=track,
            streak_days=_current_streak(self._activity.practice_days(user_id), today),
            submissions_today=self._activity.submissions_on(user_id, today),
            daily_limit=DAILY_SUBMISSION_LIMIT,
        )
