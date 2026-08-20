import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import AccountRepository, ExamTargetRepository
from argumenta.domain.accounts import ExamTarget, UserAccount
from argumenta.domain.errors import InvalidCredentialsError


@dataclass(frozen=True)
class MeView:
    user: UserAccount
    targets: list[ExamTarget]


class GetMeUseCase:
    def __init__(self, accounts: AccountRepository, targets: ExamTargetRepository) -> None:
        self._accounts = accounts
        self._targets = targets

    def execute(self, user_id: uuid.UUID) -> MeView:
        user = self._accounts.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError
        return MeView(user=user, targets=self._targets.list_for_user(user_id))
