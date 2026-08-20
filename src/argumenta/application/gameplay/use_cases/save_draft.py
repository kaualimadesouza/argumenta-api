import uuid

from argumenta.application.gameplay.ports import DraftRepository, ProgressWriter
from argumenta.domain.submission import submission_context_for


class SaveDraftUseCase:
    """Autosave: only chapters that currently accept text keep a draft."""

    def __init__(self, drafts: DraftRepository, progress: ProgressWriter) -> None:
        self._drafts = drafts
        self._progress = progress

    def execute(self, user_id: uuid.UUID, chapter_id: uuid.UUID, body: str) -> None:
        status = self._progress.status_of(user_id, chapter_id)
        submission_context_for(status)  # raises when the chapter is not writable
        self._drafts.save(user_id, chapter_id, body)
