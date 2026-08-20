from dataclasses import dataclass
from datetime import UTC, datetime

from argumenta.application.accounts.ports import AccountRepository, GoogleIdentityGateway
from argumenta.domain.accounts import UserAccount
from argumenta.domain.errors import InvalidCredentialsError


@dataclass(frozen=True)
class LoginWithGoogle:
    code: str
    redirect_uri: str


class LoginWithGoogleUseCase:
    """Creates the account on first sign-in, or links the Google identity to the
    existing user when the (verified) e-mail matches; Google is also the account
    recovery path in the beta, since there is no password reset."""

    def __init__(self, accounts: AccountRepository, google: GoogleIdentityGateway) -> None:
        self._accounts = accounts
        self._google = google

    def execute(self, request: LoginWithGoogle) -> UserAccount:
        identity = self._google.exchange_code(request.code, request.redirect_uri)
        if not identity.email_verified:
            raise InvalidCredentialsError
        user = self._accounts.find_user_by_google_subject(identity.subject)
        if user is not None:
            return user
        user = self._accounts.get_by_email(identity.email)
        if user is None:
            nickname = identity.email.split("@", 1)[0]
            user = self._accounts.create_user(
                email=identity.email,
                nickname=nickname,
                terms_accepted_at=datetime.now(tz=UTC),
            )
        self._accounts.add_google_identity(user.id, identity.subject)
        return user
