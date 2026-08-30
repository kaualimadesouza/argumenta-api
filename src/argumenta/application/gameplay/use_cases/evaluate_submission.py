import uuid
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
    ProgressWriter,
    SubmissionRepository,
)
from argumenta.domain.enums import ChapterStatus, SubmissionStatus, Verdict
from argumenta.domain.errors import ChapterNotFoundError, SubmissionNotFoundError
from argumenta.domain.lenses import DEFAULT_EXAM, grading_spec, project_lens
from argumenta.domain.submission import resolve_status_after_evaluation


class EvaluateSubmissionUseCase:
    """The correction leg of the async flow: run the pipeline for a pending
    submission, freeze the result and advance the chapter state machine.
    Idempotent: a redelivered event finds the submission no longer evaluating
    and does nothing."""

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

    def execute(self, submission_id: uuid.UUID) -> None:
        record = self._submissions.get_record(submission_id)
        if record is None:
            raise SubmissionNotFoundError(f"submission {submission_id} not found")
        if record.status != SubmissionStatus.EVALUATING:
            return
        context = self._contexts.get_context(record.chapter_id)
        if context is None:
            raise ChapterNotFoundError

        chapter = context.chapter
        exam = self._exams.active_exam(record.user_id) or DEFAULT_EXAM
        outcome = self._evaluate.execute(
            EvaluateArgument(
                text=record.body,
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
        self._submissions.store_evaluation(submission_id, outcome, context.ruler, lens)

        current = self._progress.status_of(record.user_id, record.chapter_id)
        if current == ChapterStatus.PASSED:
            # late verdict on a closed chapter: stored for history, changes nothing
            return
        passed = outcome.verdict == Verdict.APPROVED
        self._progress.apply_result(
            user_id=record.user_id,
            chapter_id=record.chapter_id,
            status=resolve_status_after_evaluation(current, outcome.verdict),
            passing_submission_id=submission_id if passed else None,
            at=datetime.now(tz=UTC),
        )
        if passed:
            # the streak day is the submission's, not the verdict's: an
            # evaluation landing after midnight must hit the row that exists
            self._activity.register_approval(record.user_id, record.submitted_at.date())
            self._drafts.discard(record.user_id, record.chapter_id)
