import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from argumenta.application.gameplay.ports import PastAttempt
from argumenta.domain.enums import Verdict
from argumenta.domain.evaluation import ScoredDimension
from argumenta.domain.lenses import DEFAULT_EXAM, LensView, project_lens


@dataclass(frozen=True)
class PastAttemptView:
    submission_id: uuid.UUID
    attempt_number: int
    body: str
    verdict: Verdict
    average_score: float
    floor_value: int
    min_average: int
    scores: tuple[ScoredDimension, ...]
    lens: LensView
    created_at: datetime


class SubmissionHistoryRepository(Protocol):
    def list_attempts(
        self, user_id: uuid.UUID, chapter_id: uuid.UUID
    ) -> tuple[PastAttempt, ...]: ...


@dataclass(frozen=True)
class GetSubmissionHistoryUseCase:
    submissions: SubmissionHistoryRepository

    def execute(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> tuple[PastAttemptView, ...]:
        attempts = self.submissions.list_attempts(user_id, chapter_id)
        views = []
        for a in attempts:
            views.append(
                PastAttemptView(
                    submission_id=a.submission_id,
                    attempt_number=a.attempt_number,
                    body=a.body,
                    verdict=a.verdict,
                    average_score=a.average_score,
                    floor_value=a.floor_value,
                    min_average=a.min_average,
                    scores=a.scores,
                    lens=project_lens(a.scores, a.exam or DEFAULT_EXAM, a.chapter_kind),
                    created_at=a.submitted_at,
                )
            )
        return tuple(views)
