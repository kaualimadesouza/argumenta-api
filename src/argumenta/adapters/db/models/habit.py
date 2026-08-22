import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from argumenta.adapters.db.base import AuditMixin, Base


class DailyActivity(AuditMixin, Base):
    """Fonte do streak e do limite diario de 3 correcoes (UPSERT atomico);
    PK composta, reativacao pos soft delete e UPDATE, nunca INSERT."""

    __tablename__ = "daily_activity"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    activity_date: Mapped[date] = mapped_column(Date, primary_key=True)
    submissions_count: Mapped[int] = mapped_column(
        SmallInteger, server_default=text("0"), nullable=False, comment="limite diario de 3"
    )
    approved_count: Mapped[int] = mapped_column(
        SmallInteger, server_default=text("0"), nullable=False
    )


class TelemetryEvent(AuditMixin, Base):
    __tablename__ = "telemetry_events"
    __table_args__ = (Index("ix_telemetry_events_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(
        BigInteger, Identity(), primary_key=True, comment="identity, alto volume"
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(
        Text, nullable=False, comment="paste, typing_stats, screen_view"
    )
    occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="hora no cliente; created_at e a hora do flush",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="unico jsonb do modelo"
    )
