import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from argumenta.domain.accounts import ExamTarget, GoogleIdentity, UserAccount
from argumenta.domain.enums import Exam
from argumenta.domain.privacy import PurgeReport


class AccountRepository(Protocol):
    def get_by_email(self, email: str) -> UserAccount | None: ...

    def get_by_id(self, user_id: uuid.UUID) -> UserAccount | None: ...

    def create_user(
        self, email: str, nickname: str, terms_accepted_at: datetime
    ) -> UserAccount: ...

    def add_email_identity(self, user_id: uuid.UUID, password_hash: str) -> None: ...

    def add_google_identity(self, user_id: uuid.UUID, subject: str) -> None: ...

    def get_email_password_hash(self, user_id: uuid.UUID) -> str | None: ...

    def find_user_by_google_subject(self, subject: str) -> UserAccount | None: ...

    def update_nickname(self, user_id: uuid.UUID, nickname: str) -> UserAccount | None:
        """None when there is no live account with that id."""
        ...

    def is_active(self, user_id: uuid.UUID) -> bool:
        """Tokens are stateless, so this is what ends a session: every request
        asks whether the account is still there."""
        ...

    def soft_delete(self, user_id: uuid.UUID) -> datetime | None:
        """Marks the account deleted and returns when; None when it was already
        gone, which is a race between two requests of the same student."""
        ...

    def retire_credentials(self, user_id: uuid.UUID) -> None:
        """Identities and push devices stop working at once. Not only hygiene:
        a live identity row would refuse the same Google account signing up
        again, and a live device token would keep getting notifications."""
        ...


class AccountPurger(Protocol):
    def due_for_purge(self, cutoff: datetime, limit: int) -> Sequence[uuid.UUID]: ...

    def purge(self, user_id: uuid.UUID) -> PurgeReport:
        """Hard delete of the user row; every dependent leaves by cascade."""
        ...


class ExamTargetRepository(Protocol):
    def list_for_user(self, user_id: uuid.UUID) -> list[ExamTarget]: ...

    def active_exam(self, user_id: uuid.UUID) -> Exam | None:
        """Which lens the student reads their corrections in; None until they
        pick a target."""
        ...

    def get(self, user_id: uuid.UUID, target_id: uuid.UUID) -> ExamTarget | None: ...

    def exists(self, user_id: uuid.UUID, exam: Exam, year: int) -> bool: ...

    def add(self, user_id: uuid.UUID, exam: Exam, year: int, is_active: bool) -> ExamTarget: ...

    def soft_delete(self, user_id: uuid.UUID, target_id: uuid.UUID) -> None: ...

    def set_active(self, user_id: uuid.UUID, target_id: uuid.UUID) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class GoogleIdentityGateway(Protocol):
    def exchange_code(self, code: str, redirect_uri: str) -> GoogleIdentity: ...
