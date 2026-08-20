import uuid
from dataclasses import dataclass

from argumenta.application.track.ports import ContentRepository, ProgressRepository
from argumenta.domain.enums import Branch, ChapterStatus
from argumenta.domain.errors import ChapterLockedError, ChapterNotFoundError
from argumenta.domain.track import BeatContent, ChapterContent, branch_for_status


@dataclass(frozen=True)
class ChapterScript:
    chapter: ChapterContent
    status: ChapterStatus
    branch: Branch
    beats: list[BeatContent]


class GetChapterUseCase:
    def __init__(self, content: ContentRepository, progress: ProgressRepository) -> None:
        self._content = content
        self._progress = progress

    def execute(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> ChapterScript:
        chapter = self._content.get_chapter(chapter_id)
        if chapter is None:
            raise ChapterNotFoundError
        status = self._progress.statuses_for_user(user_id).get(
            chapter_id, ChapterStatus.LOCKED
        )
        if status == ChapterStatus.LOCKED:
            raise ChapterLockedError
        branch = branch_for_status(status)
        return ChapterScript(
            chapter=chapter,
            status=status,
            branch=branch,
            beats=self._content.list_beats(chapter_id, branch),
        )
