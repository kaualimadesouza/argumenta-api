import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from argumenta.adapters.db.base import Base
from argumenta.adapters.db.models import AuthIdentity, PushDevice, User, UserExamTarget
from argumenta.adapters.db.user_data import DIRECT_USER_TIES, UserFk
from argumenta.domain.accounts import ExamTarget, UserAccount
from argumenta.domain.enums import AuthProvider, Exam
from argumenta.domain.privacy import PurgeReport


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

    def update_nickname(self, user_id: uuid.UUID, nickname: str) -> UserAccount | None:
        row = self._session.scalar(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(nickname=nickname)
            .returning(User)
        )
        return _to_user_account(row) if row else None

    def add_email_identity(self, user_id: uuid.UUID, password_hash: str) -> None:
        self._session.add(
            AuthIdentity(user_id=user_id, provider=AuthProvider.EMAIL, password_hash=password_hash)
        )
        self._session.flush()

    def add_google_identity(self, user_id: uuid.UUID, subject: str) -> None:
        self._session.add(
            AuthIdentity(user_id=user_id, provider=AuthProvider.GOOGLE, provider_subject=subject)
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

    def is_active(self, user_id: uuid.UUID) -> bool:
        """One indexed lookup per authenticated request: the price of ending a
        session without a server side session store."""
        return (
            self._session.scalar(
                select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
            )
            is not None
        )

    def soft_delete(self, user_id: uuid.UUID) -> datetime | None:
        stamped = self._session.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .returning(User.deleted_at)
        ).scalar_one_or_none()
        self._session.flush()
        return stamped

    def retire_credentials(self, user_id: uuid.UUID) -> None:
        now = datetime.now(tz=UTC)
        for model in (AuthIdentity, PushDevice):
            self._session.execute(
                update(model)
                .where(model.user_id == user_id, model.deleted_at.is_(None))
                .values(deleted_at=now)
            )
        self._session.flush()

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

    def active_exam(self, user_id: uuid.UUID) -> Exam | None:
        return self._session.scalar(
            select(UserExamTarget.exam).where(
                UserExamTarget.user_id == user_id,
                UserExamTarget.is_active.is_(True),
                UserExamTarget.deleted_at.is_(None),
            )
        )

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


class SqlAlchemyAccountPurger:
    """LGPD erasure is a hard delete: the universal soft delete (DER decision 8)
    is what the purge exists to undo. Dependents leave by cascade, and
    tests/test_schema_conventions.py holds the schema to that."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def due_for_purge(self, cutoff: datetime, limit: int) -> Sequence[uuid.UUID]:
        return list(
            self._session.scalars(
                select(User.id)
                .where(User.deleted_at.is_not(None), User.deleted_at <= cutoff)
                .order_by(User.deleted_at)
                .limit(limit)
            )
        )

    def purge(self, user_id: uuid.UUID) -> PurgeReport:
        """Counted before the delete, because after it there is nothing to count
        and an erasure nobody can account for is not much of an erasure."""
        rows = {tie.table: self._rows_of(tie, user_id) for tie in DIRECT_USER_TIES}
        erased = cast(
            CursorResult[Any], self._session.execute(delete(User).where(User.id == user_id))
        )
        rows["users"] = erased.rowcount
        self._session.flush()
        return PurgeReport(user_id=user_id, rows_by_table=rows)

    def _rows_of(self, tie: UserFk, user_id: uuid.UUID) -> int:
        table = Base.metadata.tables[tie.table]
        counted = self._session.scalar(
            select(func.count()).select_from(table).where(table.c[tie.column] == user_id)
        )
        return int(counted or 0)


class SqlAlchemyPushDeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def register(self, user_id: uuid.UUID, platform: Any, token: str) -> None:
        from sqlalchemy.dialects.postgresql import insert

        stmt = (
            insert(PushDevice)
            .values(user_id=user_id, platform=platform, token=token)
            .on_conflict_do_update(
                index_elements=["token"],
                index_where=PushDevice.deleted_at.is_(None),
                set_={"user_id": user_id, "platform": platform},
            )
        )
        self._session.execute(stmt)
        self._session.flush()

    def unregister(self, user_id: uuid.UUID, token: str) -> None:
        self._session.execute(
            update(PushDevice)
            .where(
                PushDevice.user_id == user_id,
                PushDevice.token == token,
                PushDevice.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        self._session.flush()

    def unregister_many(self, tokens: Sequence[str]) -> None:
        if not tokens:
            return
        self._session.execute(
            update(PushDevice)
            .where(PushDevice.token.in_(tokens), PushDevice.deleted_at.is_(None))
            .values(deleted_at=func.now())
        )
        self._session.flush()

    def get_tokens_for_users(self, user_ids: Sequence[uuid.UUID]) -> Sequence[str]:
        if not user_ids:
            return []
        rows = self._session.scalars(
            select(PushDevice.token).where(
                PushDevice.user_id.in_(user_ids), PushDevice.deleted_at.is_(None)
            )
        )
        return list(rows)
