import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from argumenta.adapters.db.models import (
    Chapter,
    ChapterBeat,
    ChapterProgress,
    Character,
    DailyActivity,
    Story,
)
from argumenta.domain.enums import Branch, ChapterStatus, ContentStatus
from argumenta.domain.track import BeatContent, ChapterContent, StorySummary


class SqlAlchemyContentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_published_stories(self) -> list[StorySummary]:
        stories = self._session.scalars(
            select(Story)
            .where(Story.status == ContentStatus.PUBLISHED, Story.deleted_at.is_(None))
            .order_by(Story.position)
        ).all()
        chapters = self._session.execute(
            select(Chapter.story_id, Chapter.id)
            .where(
                Chapter.story_id.in_([story.id for story in stories]),
                Chapter.deleted_at.is_(None),
            )
            .order_by(Chapter.story_id, Chapter.position)
        ).all()
        by_story: dict[uuid.UUID, list[uuid.UUID]] = {}
        for story_id, chapter_id in chapters:
            by_story.setdefault(story_id, []).append(chapter_id)
        return [
            StorySummary(
                id=story.id,
                slug=story.slug,
                title=story.title,
                synopsis=story.synopsis,
                position=story.position,
                is_tutorial=story.is_tutorial,
                cover_asset=story.cover_asset,
                chapter_ids=tuple(by_story.get(story.id, [])),
            )
            for story in stories
        ]

    def get_chapter(self, chapter_id: uuid.UUID) -> ChapterContent | None:
        antagonist = aliased(Character)
        row = self._session.execute(
            select(Chapter, antagonist.name, antagonist.portrait_asset)
            .join(antagonist, Chapter.antagonist_id == antagonist.id)
            .where(Chapter.id == chapter_id, Chapter.deleted_at.is_(None))
        ).first()
        if row is None:
            return None
        chapter, antagonist_name, antagonist_portrait = row
        return ChapterContent(
            id=chapter.id,
            story_id=chapter.story_id,
            position=chapter.position,
            kind=chapter.kind,
            title=chapter.title,
            objective=chapter.objective,
            min_words=chapter.min_words,
            max_words=chapter.max_words,
            antagonist_name=antagonist_name,
            antagonist_portrait=antagonist_portrait,
        )

    def list_beats(self, chapter_id: uuid.UUID, branch: Branch) -> list[BeatContent]:
        rows = self._session.execute(
            select(ChapterBeat, Character.name, Character.portrait_asset)
            .outerjoin(Character, ChapterBeat.character_id == Character.id)
            .where(
                ChapterBeat.chapter_id == chapter_id,
                ChapterBeat.branch == branch,
                ChapterBeat.deleted_at.is_(None),
            )
            .order_by(ChapterBeat.position)
        ).all()
        return [
            BeatContent(
                beat_type=beat.beat_type,
                body=beat.body,
                character_name=name,
                character_portrait=portrait,
                illustration_asset=beat.illustration_asset,
            )
            for beat, name, portrait in rows
        ]


class SqlAlchemyProgressRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def statuses_for_user(self, user_id: uuid.UUID) -> dict[uuid.UUID, ChapterStatus]:
        rows = self._session.execute(
            select(ChapterProgress.chapter_id, ChapterProgress.status).where(
                ChapterProgress.user_id == user_id,
                ChapterProgress.deleted_at.is_(None),
            )
        ).all()
        return {chapter_id: status for chapter_id, status in rows}

    def unlock(self, user_id: uuid.UUID, chapter_id: uuid.UUID, at: datetime) -> None:
        # composite-PK table: reactivation is an UPDATE, so upsert on conflict
        statement = insert(ChapterProgress).values(
            user_id=user_id,
            chapter_id=chapter_id,
            status=ChapterStatus.AVAILABLE,
            unlocked_at=at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["user_id", "chapter_id"],
            set_={"status": ChapterStatus.AVAILABLE, "unlocked_at": at, "deleted_at": None},
            where=ChapterProgress.deleted_at.is_not(None),
        )
        self._session.execute(statement)
        self._session.flush()


class SqlAlchemyActivityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def submissions_on(self, user_id: uuid.UUID, day: date) -> int:
        count = self._session.scalar(
            select(DailyActivity.submissions_count).where(
                DailyActivity.user_id == user_id,
                DailyActivity.activity_date == day,
                DailyActivity.deleted_at.is_(None),
            )
        )
        return count or 0

    def practice_days(self, user_id: uuid.UUID) -> list[date]:
        rows = self._session.scalars(
            select(DailyActivity.activity_date)
            .where(
                DailyActivity.user_id == user_id,
                DailyActivity.submissions_count > 0,
                DailyActivity.deleted_at.is_(None),
            )
            .order_by(DailyActivity.activity_date.desc())
        )
        return list(rows)

    def get_users_with_streak_at_risk(self, today: date) -> Sequence[uuid.UUID]:
        from datetime import timedelta

        from argumenta.adapters.db.models import User

        yesterday = today - timedelta(days=1)
        practiced_yesterday = select(DailyActivity.user_id).where(
            DailyActivity.activity_date == yesterday,
            DailyActivity.submissions_count > 0,
            DailyActivity.deleted_at.is_(None),
        )
        practiced_today = select(DailyActivity.user_id).where(
            DailyActivity.activity_date == today,
            DailyActivity.submissions_count > 0,
            DailyActivity.deleted_at.is_(None),
        )
        already_reminded = select(User.id).where(
            User.last_streak_reminder_at == today,
            User.deleted_at.is_(None),
        )

        from sqlalchemy import except_

        query = except_(practiced_yesterday, practiced_today, already_reminded)
        return list(self._session.scalars(query))

    def mark_streak_reminders_sent(self, user_ids: Sequence[uuid.UUID], today: date) -> None:
        if not user_ids:
            return
        from sqlalchemy import update

        from argumenta.adapters.db.models import User

        self._session.execute(
            update(User).where(User.id.in_(user_ids)).values(last_streak_reminder_at=today)
        )
        self._session.flush()
