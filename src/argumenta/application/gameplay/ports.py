import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from argumenta.domain.enums import ChapterStatus, Exam, SubmissionContext
from argumenta.domain.evaluation import EvaluationOutcome, EvaluationRuler
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
class StoredEvaluation:
    submission_id: uuid.UUID
    evaluation_id: uuid.UUID
    attempt_number: int


class EvaluationContextRepository(Protocol):
    def get_context(self, chapter_id: uuid.UUID) -> ChapterEvaluationContext | None: ...


class ActiveExamReader(Protocol):
    """The single thing gameplay needs to know about the account: which lens
    the student reads their correction in. None until they pick a target."""

    def active_exam(self, user_id: uuid.UUID) -> Exam | None: ...


class SubmissionRepository(Protocol):
    def store(
        self,
        submission: NewSubmission,
        outcome: EvaluationOutcome,
        ruler: EvaluationRuler,
        lens: LensView,
    ) -> StoredEvaluation:
        """Persists submission + evaluation (with the ruler and the lens frozen
        into it) + scores + annotations in the current transaction;
        attempt_number is the next one for the user/chapter pair."""
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


class DraftRepository(Protocol):
    def save(self, user_id: uuid.UUID, chapter_id: uuid.UUID, body: str) -> None: ...

    def get(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> str | None: ...

    def discard(self, user_id: uuid.UUID, chapter_id: uuid.UUID) -> None: ...
