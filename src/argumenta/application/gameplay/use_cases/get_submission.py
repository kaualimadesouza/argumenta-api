import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argumenta.application.gameplay.ports import ProgressWriter, SubmissionRepository
from argumenta.domain.enums import ChapterStatus, SubmissionStatus, Verdict
from argumenta.domain.errors import SubmissionNotFoundError
from argumenta.domain.evaluation import Annotation, ScoredDimension
from argumenta.domain.lenses import DEFAULT_EXAM, LensView, project_lens


@dataclass(frozen=True)
class CorrectionView:
    verdict: Verdict
    average_score: float
    floor_value: int
    min_average: int
    chapter_status: ChapterStatus
    scores: tuple[ScoredDimension, ...]
    annotations: tuple[Annotation, ...]
    lens: LensView


@dataclass(frozen=True)
class SubmissionView:
    submission_id: uuid.UUID
    chapter_id: uuid.UUID
    attempt_number: int
    status: SubmissionStatus
    result: CorrectionView | None


class GetSubmissionUseCase:
    """The polling read: owner-scoped, and a submission stuck in evaluating
    beyond the deadline reports failed, so the client is never left hanging
    (a very late worker may still land the verdict afterwards)."""

    def __init__(
        self,
        submissions: SubmissionRepository,
        progress: ProgressWriter,
        stale_after: timedelta,
    ) -> None:
        self._submissions = submissions
        self._progress = progress
        self._stale_after = stale_after

    def execute(self, user_id: uuid.UUID, submission_id: uuid.UUID) -> SubmissionView:
        record = self._submissions.get_record_for(user_id, submission_id)
        if record is None:
            raise SubmissionNotFoundError("submission not found for this user")

        status = record.status
        result = None
        if status == SubmissionStatus.EVALUATED:
            correction = self._submissions.get_correction(submission_id)
            if correction is not None:
                exam = correction.exam or DEFAULT_EXAM
                result = CorrectionView(
                    verdict=correction.verdict,
                    average_score=correction.average_score,
                    floor_value=correction.floor_value,
                    min_average=correction.min_average,
                    chapter_status=self._progress.status_of(user_id, record.chapter_id),
                    scores=correction.scores,
                    annotations=correction.annotations,
                    lens=project_lens(correction.scores, exam, correction.chapter_kind),
                )
        elif status == SubmissionStatus.EVALUATING:
            if datetime.now(tz=UTC) - record.submitted_at > self._stale_after:
                status = SubmissionStatus.FAILED
        return SubmissionView(
            submission_id=record.submission_id,
            chapter_id=record.chapter_id,
            attempt_number=record.attempt_number,
            status=status,
            result=result,
        )
