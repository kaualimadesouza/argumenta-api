"""How a story is written into the content tables, once, for every story.
Idempotent by slug: an existing story (not soft deleted) is left alone, so the
seed is safe to run on every deploy."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Chapter, ChapterBeat, Character, Story, Theme
from argumenta.domain.enums import BeatType, Branch, ChapterKind, ContentStatus, Exam


@dataclass(frozen=True)
class BeatSeed:
    branch: Branch
    beat_type: BeatType
    body: str
    character: str | None = None


@dataclass(frozen=True)
class ChapterSeed:
    kind: ChapterKind
    title: str
    objective: str
    antagonist: str
    min_words: int
    max_words: int
    evaluator_brief: str
    beats: tuple[BeatSeed, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ThemeSeed:
    """The real exam theme, with the statement rewritten in our own words."""

    exam: Exam
    year: int
    title: str
    statement: str


@dataclass(frozen=True)
class StorySeed:
    slug: str
    title: str
    synopsis: str
    position: int
    dimension_floor: int
    min_average: int
    characters: dict[str, str]
    chapters: tuple[ChapterSeed, ...]
    theme: ThemeSeed | None = None
    is_tutorial: bool = False


def insert_story(session: Session, seed: StorySeed) -> bool:
    """Inserts the whole story; returns False when its slug is already there."""
    existing = session.scalar(
        select(Story.id).where(Story.slug == seed.slug, Story.deleted_at.is_(None))
    )
    if existing is not None:
        return False

    story = Story(
        theme_id=_theme_id(session, seed.theme),
        slug=seed.slug,
        title=seed.title,
        synopsis=seed.synopsis,
        position=seed.position,
        is_tutorial=seed.is_tutorial,
        dimension_floor=seed.dimension_floor,
        min_average=seed.min_average,
        status=ContentStatus.PUBLISHED,
    )
    session.add(story)
    session.flush()

    characters = {
        name: Character(story_id=story.id, name=name, persona_brief=persona)
        for name, persona in seed.characters.items()
    }
    session.add_all(characters.values())
    session.flush()

    for position, chapter_seed in enumerate(seed.chapters, start=1):
        _insert_chapter(session, story, position, chapter_seed, characters)
    session.flush()
    return True


def _theme_id(session: Session, theme: ThemeSeed | None) -> uuid.UUID | None:
    """Reused across stories of the same exam and year: the theme is the real
    prompt, not a property of one story."""
    if theme is None:
        return None
    existing = session.scalar(
        select(Theme.id).where(
            Theme.exam == theme.exam,
            Theme.year == theme.year,
            Theme.title == theme.title,
            Theme.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return existing
    row = Theme(exam=theme.exam, year=theme.year, title=theme.title, statement=theme.statement)
    session.add(row)
    session.flush()
    return row.id


def _insert_chapter(
    session: Session,
    story: Story,
    position: int,
    seed: ChapterSeed,
    characters: dict[str, Character],
) -> None:
    chapter = Chapter(
        story_id=story.id,
        position=position,
        kind=seed.kind,
        title=seed.title,
        objective=seed.objective,
        antagonist_id=characters[seed.antagonist].id,
        min_words=seed.min_words,
        max_words=seed.max_words,
        evaluator_brief=seed.evaluator_brief,
    )
    session.add(chapter)
    session.flush()
    positions: dict[Branch, int] = {}
    for beat in seed.beats:
        positions[beat.branch] = positions.get(beat.branch, 0) + 1
        session.add(
            ChapterBeat(
                chapter_id=chapter.id,
                branch=beat.branch,
                position=positions[beat.branch],
                beat_type=beat.beat_type,
                character_id=(characters[beat.character].id if beat.character else None),
                body=beat.body,
            )
        )
