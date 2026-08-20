import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import ExamTargetRepository
from argumenta.domain.errors import ExamTargetNotFoundError


@dataclass(frozen=True)
class SetActiveExamTarget:
    user_id: uuid.UUID
    target_id: uuid.UUID


class SetActiveExamTargetUseCase:
    def __init__(self, targets: ExamTargetRepository) -> None:
        self._targets = targets

    def execute(self, request: SetActiveExamTarget) -> None:
        if self._targets.get(request.user_id, request.target_id) is None:
            raise ExamTargetNotFoundError
        self._targets.set_active(request.user_id, request.target_id)
