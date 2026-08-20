import uuid
from datetime import date, datetime
from typing import Protocol

from argumenta.domain.enums import Branch, ChapterStatus
from argumenta.domain.track import BeatContent, ChapterContent, StorySummary


class ContentRepository(Protocol):
    def list_published_stories(self) -> list[StorySummary]: ...

    def get_chapter(self, chapter_id: uuid.UUID) -> ChapterContent | None: ...

    def list_beats(self, chapter_id: uuid.UUID, branch: Branch) -> list[BeatContent]: ...


class ProgressRepository(Protocol):
    def statuses_for_user(self, user_id: uuid.UUID) -> dict[uuid.UUID, ChapterStatus]: ...

    def unlock(self, user_id: uuid.UUID, chapter_id: uuid.UUID, at: datetime) -> None:
        """Create (or reactivate) the progress row as available."""
        ...


class ActivityRepository(Protocol):
    def submissions_on(self, user_id: uuid.UUID, day: date) -> int: ...

    def practice_days(self, user_id: uuid.UUID) -> list[date]:
        """Days with at least one submission, most recent first."""
        ...
