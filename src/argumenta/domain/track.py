import enum
import uuid
from dataclasses import dataclass

from argumenta.domain.enums import BeatType, Branch, ChapterKind, ChapterStatus


class StoryState(enum.StrEnum):
    """Derived, never persisted: chapter_progress is the only state machine."""

    LOCKED = "locked"
    AVAILABLE = "available"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True)
class StorySummary:
    id: uuid.UUID
    slug: str
    title: str
    synopsis: str
    position: int
    is_tutorial: bool
    cover_asset: str | None
    chapter_ids: tuple[uuid.UUID, ...]
    """Chapter ids in position order."""


@dataclass(frozen=True)
class BeatContent:
    beat_type: BeatType
    body: str
    character_name: str | None
    character_portrait: str | None
    illustration_asset: str | None


@dataclass(frozen=True)
class ChapterContent:
    id: uuid.UUID
    story_id: uuid.UUID
    position: int
    kind: ChapterKind
    title: str
    objective: str
    min_words: int
    max_words: int
    antagonist_name: str
    antagonist_portrait: str | None


def branch_for_status(status: ChapterStatus) -> Branch:
    """Which script branch the student sees, given where they are."""
    if status == ChapterStatus.IN_CONSEQUENCE:
        return Branch.CONSEQUENCE
    if status == ChapterStatus.IN_RECOVERY:
        return Branch.RECOVERY
    return Branch.MAIN


_STARTED = (
    ChapterStatus.DRAFTING,
    ChapterStatus.IN_CONSEQUENCE,
    ChapterStatus.IN_RECOVERY,
    ChapterStatus.PASSED,
)


def derive_story_state(
    chapter_ids: tuple[uuid.UUID, ...],
    progress: dict[uuid.UUID, ChapterStatus],
    previous_completed: bool,
) -> StoryState:
    """Story state is a pure fold over its chapters' progress. A story with a
    chapter merely unlocked (available) is still AVAILABLE; it only turns
    IN_PROGRESS once the student actually starts writing or passes something."""
    statuses = [progress.get(chapter_id, ChapterStatus.LOCKED) for chapter_id in chapter_ids]
    if statuses and all(status == ChapterStatus.PASSED for status in statuses):
        return StoryState.COMPLETED
    if any(status in _STARTED for status in statuses):
        return StoryState.IN_PROGRESS
    if any(status == ChapterStatus.AVAILABLE for status in statuses) or previous_completed:
        return StoryState.AVAILABLE
    return StoryState.LOCKED


def next_playable_chapter(
    stories: list[StorySummary],
    progress: dict[uuid.UUID, ChapterStatus],
) -> uuid.UUID | None:
    """The first chapter, in track order, that the student may start but has no
    unlocked progress row yet; None when everything is either unlocked or gated."""
    previous_chapter_passed = True
    for story in stories:
        for chapter_id in story.chapter_ids:
            status = progress.get(chapter_id, ChapterStatus.LOCKED)
            if status == ChapterStatus.PASSED:
                previous_chapter_passed = True
                continue
            if status != ChapterStatus.LOCKED:
                return None
            return chapter_id if previous_chapter_passed else None
    return None
