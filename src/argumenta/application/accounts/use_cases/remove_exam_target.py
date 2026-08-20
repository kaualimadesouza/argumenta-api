import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import ExamTargetRepository
from argumenta.domain.errors import ExamTargetNotFoundError


@dataclass(frozen=True)
class RemoveExamTarget:
    user_id: uuid.UUID
    target_id: uuid.UUID


class RemoveExamTargetUseCase:
    def __init__(self, targets: ExamTargetRepository) -> None:
        self._targets = targets

    def execute(self, request: RemoveExamTarget) -> None:
        if self._targets.get(request.user_id, request.target_id) is None:
            raise ExamTargetNotFoundError
        self._targets.soft_delete(request.user_id, request.target_id)
