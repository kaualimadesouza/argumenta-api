import uuid

from sqlalchemy import Boolean, ForeignKey, Index, SmallInteger, Text, false, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from argumenta.adapters.db.base import AuditMixin, Base, UuidPkMixin, db_enum
from argumenta.adapters.db.enums import BeatType, Branch, ChapterKind, ContentStatus, Exam


class Theme(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "themes"

    exam: Mapped[Exam] = mapped_column(db_enum(Exam, "exam"), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, comment="tema real que caiu")
    statement: Mapped[str] = mapped_column(Text, nullable=False, comment="enunciado reescrito")


class Story(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "stories"
    __table_args__ = (
        Index("uq_stories_slug", "slug", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index(
            "uq_stories_position",
            "position",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    theme_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("themes.id", ondelete="SET NULL"),
        nullable=True,
        comment="null no tutorial",
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    synopsis: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="ordem na trilha")
    is_tutorial: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    dimension_floor: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="piso por dimensao 0-100"
    )
    min_average: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="media minima 0-100"
    )
    cover_asset: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ContentStatus] = mapped_column(
        db_enum(ContentStatus, "content_status"),
        server_default=ContentStatus.DRAFT.value,
        nullable=False,
    )


class Character(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "characters"

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    persona_brief: Mapped[str] = mapped_column(
        Text, nullable=False, comment="voz do personagem para a IA"
    )
    portrait_asset: Mapped[str | None] = mapped_column(Text, nullable=True)


class Chapter(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        Index(
            "uq_chapters_story_position",
            "story_id",
            "position",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    kind: Mapped[ChapterKind] = mapped_column(db_enum(ChapterKind, "chapter_kind"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(
        Text, nullable=False, comment="o que o aluno deve alcancar"
    )
    antagonist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="RESTRICT"),
        nullable=False,
        comment="quem convencer",
    )
    min_words: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_words: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    evaluator_brief: Mapped[str] = mapped_column(
        Text, nullable=False, comment="o que e argumento viavel aqui"
    )


class ChapterBeat(UuidPkMixin, AuditMixin, Base):
    __tablename__ = "chapter_beats"
    __table_args__ = (
        Index(
            "uq_chapter_beats_chapter_branch_position",
            "chapter_id",
            "branch",
            "position",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )
    branch: Mapped[Branch] = mapped_column(db_enum(Branch, "branch"), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    beat_type: Mapped[BeatType] = mapped_column(db_enum(BeatType, "beat_type"), nullable=False)
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="RESTRICT"),
        nullable=True,
        comment="so em dialogue",
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    illustration_asset: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="cena ilustrada"
    )
