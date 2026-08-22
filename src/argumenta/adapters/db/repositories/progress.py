import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import (
    Chapter,
    ChapterProgress,
    Evaluation,
    EvaluationAnnotation,
    EvaluationScore,
    Submission,
)
from argumenta.domain.enums import AnnotationType, ChapterKind, ChapterStatus
from argumenta.domain.progress import DimensionSample


class SqlAlchemyStatsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def dimension_history(self, user_id: uuid.UUID, since: datetime) -> list[DimensionSample]:
        rows = self._session.execute(
            select(EvaluationScore.dimension, Submission.created_at, EvaluationScore.score)
            .join(Evaluation, Evaluation.id == EvaluationScore.evaluation_id)
            .join(Submission, Submission.id == Evaluation.submission_id)
            .where(
                Submission.user_id == user_id,
                Submission.created_at >= since,
                Evaluation.is_current.is_(True),
                Submission.deleted_at.is_(None),
                Evaluation.deleted_at.is_(None),
                EvaluationScore.deleted_at.is_(None),
            )
            .order_by(Submission.created_at)
        ).all()
        return [
            DimensionSample(dimension=dimension, day=created_at.date(), score=score)
            for dimension, created_at, score in rows
        ]

    def repertoire_praises(self, user_id: uuid.UUID) -> int:
        return self._count(
            select(func.count())
            .select_from(EvaluationAnnotation)
            .join(Evaluation, Evaluation.id == EvaluationAnnotation.evaluation_id)
            .join(Submission, Submission.id == Evaluation.submission_id)
            .where(
                Submission.user_id == user_id,
                EvaluationAnnotation.type == AnnotationType.REPERTOIRE_PRAISE,
                EvaluationAnnotation.deleted_at.is_(None),
                Evaluation.deleted_at.is_(None),
                Submission.deleted_at.is_(None),
            )
        )

    def passed_boss_chapters(self, user_id: uuid.UUID) -> int:
        return self._count(
            select(func.count())
            .select_from(ChapterProgress)
            .join(Chapter, Chapter.id == ChapterProgress.chapter_id)
            .where(
                ChapterProgress.user_id == user_id,
                ChapterProgress.status == ChapterStatus.PASSED,
                ChapterProgress.deleted_at.is_(None),
                Chapter.kind == ChapterKind.CHEFE,
                Chapter.deleted_at.is_(None),
            )
        )

    def _count(self, statement: Select[tuple[int]]) -> int:
        return self._session.scalar(statement) or 0
