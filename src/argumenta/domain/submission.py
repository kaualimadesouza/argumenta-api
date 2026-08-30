"""Submission rules: which chapter states accept text, and where each verdict
sends the state machine (chapter_progress is the only persisted state)."""

from dataclasses import dataclass

from argumenta.domain.enums import ChapterStatus, SubmissionContext, Verdict
from argumenta.domain.errors import ChapterNotWritableError
from argumenta.domain.evaluation import EvaluationRuler
from argumenta.domain.track import ChapterContent

WRITABLE_STATUSES = (
    ChapterStatus.AVAILABLE,
    ChapterStatus.DRAFTING,
    ChapterStatus.IN_RECOVERY,
)

DAILY_SUBMISSION_LIMIT = 3


@dataclass(frozen=True)
class ChapterEvaluationContext:
    """Everything the engine needs about the chapter, plus the frozen ruler."""

    chapter: ChapterContent
    antagonist_persona: str
    evaluator_brief: str
    ruler: EvaluationRuler


def submission_context_for(status: ChapterStatus) -> SubmissionContext:
    """Recovery scenes evaluate as recovery; everything else is the main flow.
    Raises when the chapter does not accept text in its current state."""
    if status not in WRITABLE_STATUSES:
        raise ChapterNotWritableError(f"chapter is {status.value}")
    if status == ChapterStatus.IN_RECOVERY:
        return SubmissionContext.RECOVERY
    return SubmissionContext.MAIN


def next_status_for(verdict: Verdict) -> ChapterStatus:
    """approved passes the chapter; technical failure keeps the student
    drafting with the annotated text; persuasion failure opens the
    consequence branch (recovery flow lands with issue #9)."""
    if verdict == Verdict.APPROVED:
        return ChapterStatus.PASSED
    if verdict == Verdict.FAILED_TECHNICAL:
        return ChapterStatus.DRAFTING
    return ChapterStatus.IN_CONSEQUENCE


def resolve_status_after_evaluation(current: ChapterStatus, verdict: Verdict) -> ChapterStatus:
    """Async evaluation can land after the chapter already passed (two
    submissions in flight); passed is final, a late verdict never regresses."""
    if current == ChapterStatus.PASSED:
        return ChapterStatus.PASSED
    return next_status_for(verdict)


def count_words(text: str) -> int:
    return len(text.split())


def start_recovery(status: ChapterStatus) -> ChapterStatus:
    """The "tentar reverter" action: only makes sense from the consequence
    scene, and repeating it is harmless (idempotent)."""
    if status in (ChapterStatus.IN_CONSEQUENCE, ChapterStatus.IN_RECOVERY):
        return ChapterStatus.IN_RECOVERY
    raise ChapterNotWritableError(f"recovery is not available from {status.value}")
