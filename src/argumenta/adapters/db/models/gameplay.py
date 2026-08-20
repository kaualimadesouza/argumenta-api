import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from argumenta.adapters.db.base import AuditMixin, Base, UuidPkMixin, db_enum
from argumenta.domain.enums import (
    AnnotationType,
    ChapterStatus,
    Dimension,
    ReactionBeat,
    Severity,
    SubmissionContext,
    Verdict,
)


class Submission(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index(
            "uq_submissions_user_chapter_attempt",
            "user_id",
            "chapter_id",
            "attempt_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_submissions_user_chapter", "user_id", "chapter_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    context: Mapped[SubmissionContext] = mapped_column(
        db_enum(SubmissionContext, "submission_context"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    typing_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="tempo de escrita"
    )
    paste_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"), nullable=False)


class Evaluation(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        Index(
            "uq_evaluations_current",
            "submission_id",
            unique=True,
            postgresql_where=text("is_current AND deleted_at IS NULL"),
        ),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    verdict: Mapped[Verdict] = mapped_column(db_enum(Verdict, "verdict"), nullable=False)
    average_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, comment="0-100")
    floor_value: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="piso congelado no envio"
    )
    min_average: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="media congelada no envio"
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EvaluationScore(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "evaluation_scores"
    __table_args__ = (
        Index(
            "uq_evaluation_scores_evaluation_dimension",
            "evaluation_id",
            "dimension",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_evaluation_scores_dimension", "dimension"),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[Dimension] = mapped_column(db_enum(Dimension, "dimension"), nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="0-100")
    passed_floor: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence: Mapped[str] = mapped_column(
        Text, nullable=False, comment="citacao do texto que sustenta a nota"
    )


class EvaluationAnnotation(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "evaluation_annotations"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    span_start: Mapped[int] = mapped_column(Integer, nullable=False, comment="offset no texto")
    span_end: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[AnnotationType] = mapped_column(
        db_enum(AnnotationType, "annotation_type"), nullable=False
    )
    severity: Mapped[Severity] = mapped_column(db_enum(Severity, "severity"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, comment="explicacao curta")
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True, comment="forma correta")
    priority: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="1-3 entra no para passar"
    )


class CharacterReaction(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "character_reactions"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False
    )
    beat: Mapped[ReactionBeat] = mapped_column(
        db_enum(ReactionBeat, "reaction_beat"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ChapterProgress(AuditMixin, Base):
    """Unica maquina de estados persistida (DER decision 3); PK composta, entao a
    reativacao pos soft delete e UPDATE zerando deleted_at, nunca INSERT."""

    __tablename__ = "chapter_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[ChapterStatus] = mapped_column(
        db_enum(ChapterStatus, "chapter_status"),
        server_default=ChapterStatus.LOCKED.value,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"), nullable=False)
    passing_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    unlocked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    passed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class Draft(AuditMixin, Base):
    """Rascunho com autosave, soft-deleted quando o capitulo e aprovado."""

    __tablename__ = "drafts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
