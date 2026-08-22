import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from argumenta.application.evaluation.use_cases import (
    EvaluateArgument,
    EvaluateArgumentUseCase,
)
from argumenta.application.gameplay.ports import (
    ActiveExamReader,
    DailyActivityWriter,
    DraftRepository,
    EvaluationContextRepository,
    NewSubmission,
    ProgressWriter,
    SubmissionRepository,
)
from argumenta.domain.enums import ChapterStatus, Verdict
from argumenta.domain.errors import ChapterNotFoundError, WordCountOutOfRangeError
from argumenta.domain.evaluation import EvaluationOutcome, EvaluationRuler
from argumenta.domain.lenses import (
    DEFAULT_EXAM,
    LensView,
    grading_spec,
    project_lens,
)
from argumenta.domain.submission import (
    DAILY_SUBMISSION_LIMIT,
    count_words,
    next_status_for,
    submission_context_for,
)


@dataclass(frozen=True)
class SubmitArgument:
    user_id: uuid.UUID
    chapter_id: uuid.UUID
    body: str
    typing_ms: int | None = None
    paste_count: int = 0


@dataclass(frozen=True)
class SubmissionResult:
    submission_id: uuid.UUID
    evaluation_id: uuid.UUID
    attempt_number: int
    chapter_status: ChapterStatus
    ruler: EvaluationRuler
    outcome: EvaluationOutcome
    lens: LensView
    """The same internal correction, projected into the student's exam lens."""


class SubmitArgumentUseCase:
    """The central move of the game, one transaction end to end: gate word count
    and the daily cap, run the correction pipeline, persist everything with the
    ruler frozen, and advance the chapter state machine."""

    def __init__(
        self,
        contexts: EvaluationContextRepository,
        submissions: SubmissionRepository,
        progress: ProgressWriter,
        activity: DailyActivityWriter,
        drafts: DraftRepository,
        evaluate: EvaluateArgumentUseCase,
        exams: ActiveExamReader,
    ) -> None:
        self._contexts = contexts
        self._submissions = submissions
        self._progress = progress
        self._activity = activity
        self._drafts = drafts
        self._evaluate = evaluate
        self._exams = exams

    def execute(self, request: SubmitArgument) -> SubmissionResult:
        context = self._contexts.get_context(request.chapter_id)
        if context is None:
            raise ChapterNotFoundError
        status = self._progress.status_of(request.user_id, request.chapter_id)
        submission_context = submission_context_for(status)

        word_count = count_words(request.body)
        chapter = context.chapter
        if not chapter.min_words <= word_count <= chapter.max_words:
            raise WordCountOutOfRangeError(
                f"text has {word_count} words; the chapter asks for "
                f"{chapter.min_words} to {chapter.max_words}"
            )

        now = datetime.now(tz=UTC)
        # atomic gate BEFORE the LLM spends tokens; rolls back with the request
        # transaction if anything after it fails
        self._activity.register_submission(request.user_id, now.date(), DAILY_SUBMISSION_LIMIT)

        exam = self._exams.active_exam(request.user_id) or DEFAULT_EXAM
        outcome = self._evaluate.execute(
            EvaluateArgument(
                text=request.body,
                chapter_objective=chapter.objective,
                evaluator_brief=context.evaluator_brief,
                persona_brief=context.antagonist_persona,
                min_words=chapter.min_words,
                max_words=chapter.max_words,
                ruler=context.ruler,
                spec=grading_spec(chapter.kind, exam),
            )
        )

        lens = project_lens(outcome.scores, exam, chapter.kind)
        stored = self._submissions.store(
            NewSubmission(
                user_id=request.user_id,
                chapter_id=request.chapter_id,
                context=submission_context,
                body=request.body,
                word_count=word_count,
                typing_ms=request.typing_ms,
                paste_count=request.paste_count,
            ),
            outcome,
            context.ruler,
            lens,
        )

        new_status = next_status_for(outcome.verdict)
        passed = outcome.verdict == Verdict.APPROVED
        self._progress.apply_result(
            user_id=request.user_id,
            chapter_id=request.chapter_id,
            status=new_status,
            passing_submission_id=stored.submission_id if passed else None,
            at=now,
        )
        if passed:
            self._activity.register_approval(request.user_id, now.date())
            self._drafts.discard(request.user_id, request.chapter_id)

        return SubmissionResult(
            submission_id=stored.submission_id,
            evaluation_id=stored.evaluation_id,
            attempt_number=stored.attempt_number,
            chapter_status=new_status,
            ruler=context.ruler,
            outcome=outcome,
            lens=lens,
        )
