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
from argumenta.adapters.observability import metrics as obs_metrics
from argumenta.application.gameplay.ports import (
    NewSubmission,
    PastAttempt,
    PendingSubmission,
    StoredCorrection,
    SubmissionRecord,
)
from argumenta.domain.enums import ChapterStatus, SubmissionStatus
from argumenta.domain.errors import DailyLimitReachedError
from argumenta.domain.evaluation import (
    Annotation,
    EvaluationOutcome,
    EvaluationRuler,
    ScoredDimension,
)
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

    def create_pending(self, submission: NewSubmission) -> PendingSubmission:
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
            status=SubmissionStatus.EVALUATING,
            context=submission.context,
            body=submission.body,
            word_count=submission.word_count,
            typing_ms=submission.typing_ms,
            paste_count=submission.paste_count,
        )
        self._session.add(row)
        self._session.flush()
        return PendingSubmission(submission_id=row.id, attempt_number=attempt_number)

    def get_record(self, submission_id: uuid.UUID) -> SubmissionRecord | None:
        row = self._session.scalar(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.deleted_at.is_(None),
            )
        )
        return None if row is None else self._record(row)

    def get_record_for(
        self, user_id: uuid.UUID, submission_id: uuid.UUID
    ) -> SubmissionRecord | None:
        row = self._session.scalar(
            select(Submission).where(
                Submission.id == submission_id,
                Submission.user_id == user_id,
                Submission.deleted_at.is_(None),
            )
        )
        return None if row is None else self._record(row)

    @staticmethod
    def _record(row: Submission) -> SubmissionRecord:
        return SubmissionRecord(
            submission_id=row.id,
            user_id=row.user_id,
            chapter_id=row.chapter_id,
            body=row.body,
            status=row.status,
            attempt_number=row.attempt_number,
            submitted_at=row.created_at,
        )

    def store_evaluation(
        self,
        submission_id: uuid.UUID,
        outcome: EvaluationOutcome,
        ruler: EvaluationRuler,
        lens: LensView,
    ) -> uuid.UUID:
        evaluation = Evaluation(
            submission_id=submission_id,
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
        self._set_status(submission_id, SubmissionStatus.EVALUATED)
        self._session.flush()
        # issue #51 dashboard counter, recorded where the verdict actually
        # lands now that grading is async (issue #68)
        obs_metrics.submissions_counter.add(1, {"verdict": outcome.verdict.value})
        return evaluation.id

    def mark_failed(self, submission_id: uuid.UUID) -> None:
        self._set_status(submission_id, SubmissionStatus.FAILED)
        self._session.flush()

    def _set_status(self, submission_id: uuid.UUID, status: SubmissionStatus) -> None:
        self._session.execute(
            update(Submission)
            .where(Submission.id == submission_id, Submission.deleted_at.is_(None))
            .values(status=status)
        )

    def list_attempts(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> tuple[PastAttempt, ...]:
        rows = self._session.execute(
            select(Submission, Evaluation, Chapter.kind)
            .join(Evaluation, Evaluation.submission_id == Submission.id)
            .join(Chapter, Submission.chapter_id == Chapter.id)
            .where(
                Submission.user_id == user_id,
                Submission.chapter_id == chapter_id,
                Submission.deleted_at.is_(None),
                Evaluation.is_current.is_(True),
                Evaluation.deleted_at.is_(None),
            )
            .order_by(Submission.attempt_number.desc())
        ).all()

        results = []
        for submission, evaluation, chapter_kind in rows:
            scores = tuple(
                ScoredDimension(
                    dimension=score.dimension,
                    score=score.score,
                    evidence=score.evidence,
                    passed_floor=score.passed_floor,
                )
                for score in self._session.scalars(
                    select(EvaluationScore).where(
                        EvaluationScore.evaluation_id == evaluation.id,
                        EvaluationScore.deleted_at.is_(None),
                    )
                )
            )
            results.append(
                PastAttempt(
                    submission_id=submission.id,
                    attempt_number=submission.attempt_number,
                    body=submission.body,
                    verdict=evaluation.verdict,
                    average_score=float(evaluation.average_score),
                    floor_value=evaluation.floor_value,
                    min_average=evaluation.min_average,
                    scores=scores,
                    exam=evaluation.exam,
                    chapter_kind=chapter_kind,
                    submitted_at=submission.created_at,
                )
            )
        return tuple(results)

    def get_correction(self, submission_id: uuid.UUID) -> StoredCorrection | None:
        row = self._session.execute(
            select(Evaluation, Chapter.kind)
            .join(Submission, Evaluation.submission_id == Submission.id)
            .join(Chapter, Submission.chapter_id == Chapter.id)
            .where(
                Evaluation.submission_id == submission_id,
                Evaluation.is_current.is_(True),
                Evaluation.deleted_at.is_(None),
            )
        ).first()
        if row is None:
            return None
        evaluation, chapter_kind = row
        scores = tuple(
            ScoredDimension(
                dimension=score.dimension,
                score=score.score,
                evidence=score.evidence,
                passed_floor=score.passed_floor,
            )
            for score in self._session.scalars(
                select(EvaluationScore).where(
                    EvaluationScore.evaluation_id == evaluation.id,
                    EvaluationScore.deleted_at.is_(None),
                )
            )
        )
        annotations = tuple(
            Annotation(
                span_start=annotation.span_start,
                span_end=annotation.span_end,
                type=annotation.type,
                severity=annotation.severity,
                message=annotation.message,
                suggestion=annotation.suggestion,
                priority=annotation.priority,
            )
            for annotation in self._session.scalars(
                select(EvaluationAnnotation)
                .where(
                    EvaluationAnnotation.evaluation_id == evaluation.id,
                    EvaluationAnnotation.deleted_at.is_(None),
                )
                .order_by(EvaluationAnnotation.span_start, EvaluationAnnotation.span_end)
            )
        )
        return StoredCorrection(
            verdict=evaluation.verdict,
            average_score=float(evaluation.average_score),
            floor_value=evaluation.floor_value,
            min_average=evaluation.min_average,
            scores=scores,
            annotations=annotations,
            exam=evaluation.exam,
            chapter_kind=chapter_kind,
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

    def withdraw_submission(self, user_id: uuid.UUID, day: date) -> None:
        self._session.execute(
            update(DailyActivity)
            .where(
                DailyActivity.user_id == user_id,
                DailyActivity.activity_date == day,
                DailyActivity.submissions_count > 0,
            )
            .values(submissions_count=DailyActivity.submissions_count - 1)
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
