import uuid
from datetime import date, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from argumenta.adapters.db.models import (
    Chapter,
    ChapterProgress,
    Character,
    DailyActivity,
    Draft,
    Evaluation,
    EvaluationAnnotation,
    EvaluationScore,
    Story,
    Submission,
)
from argumenta.application.gameplay.ports import NewSubmission, StoredEvaluation
from argumenta.domain.enums import ChapterStatus
from argumenta.domain.errors import DailyLimitReachedError
from argumenta.domain.evaluation import EvaluationOutcome, EvaluationRuler
from argumenta.domain.lenses import LensView
from argumenta.domain.submission import ChapterEvaluationContext
from argumenta.domain.track import ChapterContent


class SqlAlchemyEvaluationContextRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_context(self, chapter_id: uuid.UUID) -> ChapterEvaluationContext | None:
        antagonist = aliased(Character)
        row = self._session.execute(
            select(Chapter, Story, antagonist)
            .join(Story, Chapter.story_id == Story.id)
            .join(antagonist, Chapter.antagonist_id == antagonist.id)
            .where(Chapter.id == chapter_id, Chapter.deleted_at.is_(None))
        ).first()
        if row is None:
            return None
        chapter, story, character = row
        return ChapterEvaluationContext(
            chapter=ChapterContent(
                id=chapter.id,
                story_id=chapter.story_id,
                position=chapter.position,
                kind=chapter.kind,
                title=chapter.title,
                objective=chapter.objective,
                min_words=chapter.min_words,
                max_words=chapter.max_words,
                antagonist_name=character.name,
                antagonist_portrait=character.portrait_asset,
            ),
            antagonist_persona=character.persona_brief,
            evaluator_brief=chapter.evaluator_brief,
            ruler=EvaluationRuler(
                dimension_floor=story.dimension_floor, min_average=story.min_average
            ),
        )


class SqlAlchemySubmissionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def store(
        self,
        submission: NewSubmission,
        outcome: EvaluationOutcome,
        ruler: EvaluationRuler,
        lens: LensView,
    ) -> StoredEvaluation:
        attempt_number = self._session.execute(
            select(func.coalesce(func.max(Submission.attempt_number), 0) + 1).where(
                Submission.user_id == submission.user_id,
                Submission.chapter_id == submission.chapter_id,
                Submission.deleted_at.is_(None),
            )
        ).scalar_one()
        row = Submission(
            user_id=submission.user_id,
            chapter_id=submission.chapter_id,
            attempt_number=attempt_number,
            context=submission.context,
            body=submission.body,
            word_count=submission.word_count,
            typing_ms=submission.typing_ms,
            paste_count=submission.paste_count,
        )
        self._session.add(row)
        self._session.flush()

        evaluation = Evaluation(
            submission_id=row.id,
            is_current=True,
            verdict=outcome.verdict,
            average_score=outcome.average_score,
            floor_value=ruler.dimension_floor,
            min_average=ruler.min_average,
            model=outcome.model,
            prompt_version=outcome.prompt_version,
            lens_version=lens.version,
            exam=lens.exam,
            latency_ms=outcome.latency_ms,
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
        )
        self._session.add(evaluation)
        self._session.flush()

        for score in outcome.scores:
            self._session.add(
                EvaluationScore(
                    evaluation_id=evaluation.id,
                    dimension=score.dimension,
                    score=score.score,
                    passed_floor=score.passed_floor,
                    evidence=score.evidence,
                )
            )
        for annotation in outcome.annotations:
            self._session.add(
                EvaluationAnnotation(
                    evaluation_id=evaluation.id,
                    span_start=annotation.span_start,
                    span_end=annotation.span_end,
                    type=annotation.type,
                    severity=annotation.severity,
                    message=annotation.message,
                    suggestion=annotation.suggestion,
                    priority=annotation.priority,
                )
            )
        self._session.flush()
        return StoredEvaluation(
            submission_id=row.id,
            evaluation_id=evaluation.id,
            attempt_number=attempt_number,
        )


class SqlAlchemyProgressWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def status_of(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> ChapterStatus:
        status = self._session.scalar(
            select(ChapterProgress.status).where(
                ChapterProgress.user_id == user_id,
                ChapterProgress.chapter_id == chapter_id,
                ChapterProgress.deleted_at.is_(None),
            )
        )
        return status or ChapterStatus.LOCKED

    def set_status(self, user_id: uuid.UUID, chapter_id: uuid.UUID, status: ChapterStatus) -> None:
        self._session.execute(
            update(ChapterProgress)
            .where(
                ChapterProgress.user_id == user_id,
                ChapterProgress.chapter_id == chapter_id,
                ChapterProgress.deleted_at.is_(None),
            )
            .values(status=status)
        )
        self._session.flush()

    def apply_result(
        self,
        user_id: uuid.UUID,
        chapter_id: uuid.UUID,
        status: ChapterStatus,
        passing_submission_id: uuid.UUID | None,
        at: datetime,
    ) -> None:
        values: dict[str, object] = {
            "status": status,
            "attempts": ChapterProgress.attempts + 1,
        }
        if status == ChapterStatus.PASSED:
            values["passed_at"] = at
            values["passing_submission_id"] = passing_submission_id
        self._session.execute(
            update(ChapterProgress)
            .where(
                ChapterProgress.user_id == user_id,
                ChapterProgress.chapter_id == chapter_id,
                ChapterProgress.deleted_at.is_(None),
            )
            .values(**values)
        )
        self._session.flush()


class SqlAlchemyDailyActivityWriter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def register_submission(self, user_id: uuid.UUID, day: date, limit: int) -> None:
        statement = (
            insert(DailyActivity)
            .values(user_id=user_id, activity_date=day, submissions_count=1)
            .on_conflict_do_update(
                index_elements=["user_id", "activity_date"],
                set_={"submissions_count": DailyActivity.submissions_count + 1},
                where=DailyActivity.submissions_count < limit,
            )
            .returning(DailyActivity.submissions_count)
        )
        applied = self._session.execute(statement).scalar()
        if applied is None:
            raise DailyLimitReachedError(
                f"daily limit of {limit} corrections reached; come back tomorrow"
            )
        self._session.flush()

    def register_approval(self, user_id: uuid.UUID, day: date) -> None:
        self._session.execute(
            update(DailyActivity)
            .where(
                DailyActivity.user_id == user_id,
                DailyActivity.activity_date == day,
            )
            .values(approved_count=DailyActivity.approved_count + 1)
        )
        self._session.flush()


class SqlAlchemyDraftRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, user_id: uuid.UUID, chapter_id: uuid.UUID, body: str) -> None:
        statement = (
            insert(Draft)
            .values(user_id=user_id, chapter_id=chapter_id, body=body)
            .on_conflict_do_update(
                index_elements=["user_id", "chapter_id"],
                set_={"body": body, "deleted_at": None},
            )
        )
        self._session.execute(statement)
        self._session.flush()

    def get(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(Draft.body).where(
                Draft.user_id == user_id,
                Draft.chapter_id == chapter_id,
                Draft.deleted_at.is_(None),
            )
        )

    def discard(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
        self._session.execute(
            update(Draft)
            .where(
                Draft.user_id == user_id,
                Draft.chapter_id == chapter_id,
                Draft.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
        )
        self._session.flush()
