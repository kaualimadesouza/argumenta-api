import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from argumenta.domain.enums import (
    ChapterKind,
    ChapterStatus,
    Exam,
    SubmissionContext,
    SubmissionStatus,
    Verdict,
)
from argumenta.domain.evaluation import (
    Annotation,
    EvaluationOutcome,
    EvaluationRuler,
    ScoredDimension,
)
from argumenta.domain.lenses import LensView
from argumenta.domain.submission import ChapterEvaluationContext


@dataclass(frozen=True)
class NewSubmission:
    user_id: uuid.UUID
    chapter_id: uuid.UUID
    context: SubmissionContext
    body: str
    word_count: int
    typing_ms: int | None
    paste_count: int


@dataclass(frozen=True)
class PendingSubmission:
    submission_id: uuid.UUID
    attempt_number: int


@dataclass(frozen=True)
class SubmissionRecord:
    """The submission row as the worker and the polling read it."""

    submission_id: uuid.UUID
    user_id: uuid.UUID
    chapter_id: uuid.UUID
    body: str
    status: SubmissionStatus
    attempt_number: int
    submitted_at: datetime


@dataclass(frozen=True)
class StoredCorrection:
    """The frozen correction of an evaluated submission, read back for polling;
    the lens is re-projected from these scores, exam and chapter kind."""

    verdict: Verdict
    average_score: float
    floor_value: int
    min_average: int
    scores: tuple[ScoredDimension, ...]
    annotations: tuple[Annotation, ...]
    exam: Exam | None
    chapter_kind: ChapterKind


class EvaluationContextRepository(Protocol):
    def get_context(self, chapter_id: uuid.UUID) -> ChapterEvaluationContext | None: ...


class ActiveExamReader(Protocol):
    """The single thing gameplay needs to know about the account: which lens
    the student reads their correction in. None until they pick a target."""

    def active_exam(self, user_id: uuid.UUID) -> Exam | None: ...


class SubmissionRepository(Protocol):
    def create_pending(self, submission: NewSubmission) -> PendingSubmission:
        """Persists the submission with status=evaluating; attempt_number is the
        next one for the user/chapter pair."""
        ...

    def get_record(self, submission_id: uuid.UUID) -> SubmissionRecord | None: ...

    def get_record_for(
        self, user_id: uuid.UUID, submission_id: uuid.UUID
    ) -> SubmissionRecord | None:
        """Owner-scoped read: another user's submission is None, not forbidden."""
        ...

    def store_evaluation(
        self,
        submission_id: uuid.UUID,
        outcome: EvaluationOutcome,
        ruler: EvaluationRuler,
        lens: LensView,
    ) -> uuid.UUID:
        """Persists evaluation (with the ruler and the lens frozen into it) +
        scores + annotations, and flips the submission to evaluated."""
        ...

    def mark_failed(self, submission_id: uuid.UUID) -> None: ...

    def get_correction(self, submission_id: uuid.UUID) -> StoredCorrection | None:
        """The current evaluation of the submission, None while there is none."""
        ...


class EvaluationDispatcher(Protocol):
    def dispatch(self, submission_id: uuid.UUID) -> None:
        """Hands the pending submission to the evaluator. Implementations must
        make the row durable (or share the caller's transaction) before any
        out-of-process hand-off."""
        ...


class ProgressWriter(Protocol):
    def status_of(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> ChapterStatus: ...

    def set_status(self, user_id: uuid.UUID, chapter_id: uuid.UUID, status: ChapterStatus) -> None:
        """Plain status move (no attempt accounting), e.g. entering recovery."""
        ...

    def apply_result(
        self,
        user_id: uuid.UUID,
        chapter_id: uuid.UUID,
        status: ChapterStatus,
        passing_submission_id: uuid.UUID | None,
        at: datetime,
    ) -> None:
        """Moves the state machine: increments attempts, sets passed_at and the
        passing submission when the chapter is passed."""
        ...


class DailyActivityWriter(Protocol):
    def register_submission(self, user_id: uuid.UUID, day: date, limit: int) -> None:
        """Atomic upsert; raises DailyLimitReachedError at the cap."""
        ...

    def register_approval(self, user_id: uuid.UUID, day: date) -> None: ...

    def withdraw_submission(self, user_id: uuid.UUID, day: date) -> None:
        """Refunds one daily tick when the evaluation failed on our side; the
        student's 3-a-day budget only pays for corrections that happened."""
        ...


class DraftRepository(Protocol):
    def save(self, user_id: uuid.UUID, chapter_id: uuid.UUID, body: str) -> None: ...

    def get(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> str | None: ...

    def discard(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> None: ...
