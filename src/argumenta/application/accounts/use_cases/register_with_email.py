from dataclasses import dataclass
from datetime import UTC, datetime

from argumenta.application.accounts.ports import AccountRepository, PasswordHasher
from argumenta.domain.accounts import UserAccount
from argumenta.domain.errors import EmailAlreadyRegisteredError, TermsNotAcceptedError


@dataclass(frozen=True)
class RegisterWithEmail:
    email: str
    nickname: str
    password: str
    accepted_terms: bool


class RegisterWithEmailUseCase:
    def __init__(self, accounts: AccountRepository, hasher: PasswordHasher) -> None:
        self._accounts = accounts
        self._hasher = hasher

    def execute(self, request: RegisterWithEmail) -> UserAccount:
        if not request.accepted_terms:
            raise TermsNotAcceptedError
        if self._accounts.get_by_email(request.email) is not None:
            raise EmailAlreadyRegisteredError
        user = self._accounts.create_user(
            email=request.email,
            nickname=request.nickname,
            terms_accepted_at=datetime.now(tz=UTC),
        )
        self._accounts.add_email_identity(user.id, self._hasher.hash(request.password))
        return user
