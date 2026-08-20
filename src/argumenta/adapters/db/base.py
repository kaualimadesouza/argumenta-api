import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, MetaData, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UuidPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


class AuditMixin:
    """DER decision 6 and 8: every table carries created_at, updated_at and the
    universal soft delete deleted_at; updated_at is maintained by the application
    (SQLAlchemy onupdate), deleted_at by explicit soft-delete operations."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


NOT_DELETED = text("deleted_at IS NULL")


def db_enum(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Native Postgres enum storing the member VALUES (DER lowercase names),
    not the Python member names, which is SQLAlchemy's default."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
