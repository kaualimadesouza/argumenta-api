import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import AuthIdentity, User, UserExamTarget
from argumenta.domain.accounts import ExamTarget, UserAccount
from argumenta.domain.enums import AuthProvider, Exam


def _to_user_account(row: User) -> UserAccount:
    return UserAccount(
        id=row.id,
        email=row.email,
        nickname=row.nickname,
        terms_accepted_at=row.terms_accepted_at,
    )


def _to_exam_target(row: UserExamTarget) -> ExamTarget:
    return ExamTarget(id=row.id, exam=row.exam, year=row.year, is_active=row.is_active)


class SqlAlchemyAccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> UserAccount | None:
        row = self._session.scalar(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return _to_user_account(row) if row else None

    def get_by_id(self, user_id: uuid.UUID) -> UserAccount | None:
        row = self._session.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return _to_user_account(row) if row else None

    def create_user(self, email: str, nickname: str, terms_accepted_at: datetime) -> UserAccount:
        row = User(email=email, nickname=nickname, terms_accepted_at=terms_accepted_at)
        self._session.add(row)
        self._session.flush()
        return _to_user_account(row)

    def add_email_identity(self, user_id: uuid.UUID, password_hash: str) -> None:
        self._session.add(
            AuthIdentity(
                user_id=user_id, provider=AuthProvider.EMAIL, password_hash=password_hash
            )
        )
        self._session.flush()

    def add_google_identity(self, user_id: uuid.UUID, subject: str) -> None:
        self._session.add(
            AuthIdentity(
                user_id=user_id, provider=AuthProvider.GOOGLE, provider_subject=subject
            )
        )
        self._session.flush()

    def get_email_password_hash(self, user_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(AuthIdentity.password_hash).where(
                AuthIdentity.user_id == user_id,
                AuthIdentity.provider == AuthProvider.EMAIL,
                AuthIdentity.deleted_at.is_(None),
            )
        )

    def find_user_by_google_subject(self, subject: str) -> UserAccount | None:
        row = self._session.scalar(
            select(User)
            .join(AuthIdentity, AuthIdentity.user_id == User.id)
            .where(
                AuthIdentity.provider == AuthProvider.GOOGLE,
                AuthIdentity.provider_subject == subject,
                AuthIdentity.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        )
        return _to_user_account(row) if row else None


class SqlAlchemyExamTargetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: uuid.UUID) -> list[ExamTarget]:
        rows = self._session.scalars(
            select(UserExamTarget)
            .where(
                UserExamTarget.user_id == user_id,
                UserExamTarget.deleted_at.is_(None),
            )
            .order_by(UserExamTarget.year, UserExamTarget.exam)
        )
        return [_to_exam_target(row) for row in rows]

    def get(self, user_id: uuid.UUID, target_id: uuid.UUID) -> ExamTarget | None:
        row = self._session.scalar(
            select(UserExamTarget).where(
                UserExamTarget.id == target_id,
                UserExamTarget.user_id == user_id,
                UserExamTarget.deleted_at.is_(None),
            )
        )
        return _to_exam_target(row) if row else None

    def exists(self, user_id: uuid.UUID, exam: Exam, year: int) -> bool:
        row = self._session.scalar(
            select(UserExamTarget.id).where(
                UserExamTarget.user_id == user_id,
                UserExamTarget.exam == exam,
                UserExamTarget.year == year,
                UserExamTarget.deleted_at.is_(None),
            )
        )
        return row is not None

    def add(self, user_id: uuid.UUID, exam: Exam, year: int, is_active: bool) -> ExamTarget:
        row = UserExamTarget(user_id=user_id, exam=exam, year=year, is_active=is_active)
        self._session.add(row)
        self._session.flush()
        return _to_exam_target(row)

    def soft_delete(self, user_id: uuid.UUID, target_id: uuid.UUID) -> None:
        self._session.execute(
            update(UserExamTarget)
            .where(
                UserExamTarget.id == target_id,
                UserExamTarget.user_id == user_id,
                UserExamTarget.deleted_at.is_(None),
            )
            .values(deleted_at=datetime.now(tz=UTC), is_active=False)
        )
        self._session.flush()

    def set_active(self, user_id: uuid.UUID, target_id: uuid.UUID) -> None:
        # deactivate first: the partial unique allows a single active lens per user
        self._session.execute(
            update(UserExamTarget)
            .where(
                UserExamTarget.user_id == user_id,
                UserExamTarget.is_active.is_(True),
                UserExamTarget.deleted_at.is_(None),
            )
            .values(is_active=False)
        )
        self._session.execute(
            update(UserExamTarget)
            .where(
                UserExamTarget.id == target_id,
                UserExamTarget.user_id == user_id,
                UserExamTarget.deleted_at.is_(None),
            )
            .values(is_active=True)
        )
        self._session.flush()
