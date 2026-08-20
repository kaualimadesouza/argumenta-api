import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import ExamTargetRepository
from argumenta.domain.accounts import ExamTarget
from argumenta.domain.enums import Exam
from argumenta.domain.errors import ExamTargetAlreadyExistsError


@dataclass(frozen=True)
class AddExamTarget:
    user_id: uuid.UUID
    exam: Exam
    year: int


class AddExamTargetUseCase:
    def __init__(self, targets: ExamTargetRepository) -> None:
        self._targets = targets

    def execute(self, request: AddExamTarget) -> ExamTarget:
        if self._targets.exists(request.user_id, request.exam, request.year):
            raise ExamTargetAlreadyExistsError
        is_first = not self._targets.list_for_user(request.user_id)
        return self._targets.add(request.user_id, request.exam, request.year, is_active=is_first)
