import uuid

from argumenta.application.gameplay.ports import ProgressWriter
from argumenta.domain.submission import start_recovery


class StartRecoveryUseCase:
    """The student chooses to try to revert the bad consequence."""

    def __init__(self, progress: ProgressWriter) -> None:
        self._progress = progress

    def execute(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
        status = self._progress.status_of(user_id, chapter_id)
        new_status = start_recovery(status)
        if new_status != status:
            self._progress.set_status(user_id, chapter_id, new_status)
