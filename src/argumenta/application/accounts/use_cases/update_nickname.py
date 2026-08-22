import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import AccountRepository
from argumenta.domain.accounts import UserAccount
from argumenta.domain.errors import AccountNotFoundError


@dataclass(frozen=True)
class UpdateNickname:
    user_id: uuid.UUID
    nickname: str


class UpdateNicknameUseCase:
    def __init__(self, accounts: AccountRepository) -> None:
        self._accounts = accounts

    def execute(self, request: UpdateNickname) -> UserAccount:
        user = self._accounts.update_nickname(request.user_id, request.nickname)
        if user is None:
            raise AccountNotFoundError(str(request.user_id))
        return user
