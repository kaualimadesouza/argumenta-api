from dataclasses import dataclass

from argumenta.application.accounts.ports import AccountRepository, PasswordHasher
from argumenta.application.ports import RateLimiter
from argumenta.domain.accounts import UserAccount
from argumenta.domain.errors import InvalidCredentialsError, TooManyAttemptsError


@dataclass(frozen=True)
class LoginWithEmail:
    email: str
    password: str
    client_key: str
    """Rate-limit key, e.g. the caller IP; opaque to the use case."""


class LoginWithEmailUseCase:
    def __init__(
        self,
        accounts: AccountRepository,
        hasher: PasswordHasher,
        rate_limiter: RateLimiter,
    ) -> None:
        self._accounts = accounts
        self._hasher = hasher
        self._rate_limiter = rate_limiter

    def execute(self, request: LoginWithEmail) -> UserAccount:
        rate_key = f"login:{request.client_key}:{request.email}"
        if not self._rate_limiter.check(rate_key):
            raise TooManyAttemptsError
        user = self._accounts.get_by_email(request.email)
        if user is None:
            raise InvalidCredentialsError
        password_hash = self._accounts.get_email_password_hash(user.id)
        if password_hash is None or not self._hasher.verify(password_hash, request.password):
            raise InvalidCredentialsError
        self._rate_limiter.reset(rate_key)
        return user
