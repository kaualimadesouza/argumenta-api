import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Index, SmallInteger, Text, false, text
from sqlalchemy.dialects.postgresql import CITEXT, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from argumenta.adapters.db.base import AuditMixin, Base, UuidPkMixin, db_enum
from argumenta.domain.enums import AuthProvider, DevicePlatform, Exam


class User(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_email", "email", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )

    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    nickname: Mapped[str] = mapped_column(Text, nullable=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_streak_reminder_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class UserExamTarget(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "user_exam_targets"
    __table_args__ = (
        Index(
            "uq_user_exam_targets_user_exam_year",
            "user_id",
            "exam",
            "year",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_user_exam_targets_active_lens",
            "user_id",
            unique=True,
            postgresql_where=text("is_active AND deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exam: Mapped[Exam] = mapped_column(db_enum(Exam, "exam"), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)


class AuthIdentity(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "auth_identities"
    __table_args__ = (
        Index(
            "uq_auth_identities_user_provider",
            "user_id",
            "provider",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_auth_identities_provider_subject",
            "provider",
            "provider_subject",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[AuthProvider] = mapped_column(
        db_enum(AuthProvider, "auth_provider"), nullable=False
    )
    provider_subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


class PushDevice(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "push_devices"
    __table_args__ = (
        Index(
            "uq_push_devices_token",
            "token",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[DevicePlatform] = mapped_column(
        db_enum(DevicePlatform, "device_platform"), nullable=False
    )
    token: Mapped[str] = mapped_column(Text, nullable=False)
