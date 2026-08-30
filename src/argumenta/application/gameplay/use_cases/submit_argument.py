import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from argumenta.application.gameplay.ports import (
    DailyActivityWriter,
    EvaluationContextRepository,
    EvaluationDispatcher,
    NewSubmission,
    PendingSubmission,
    ProgressWriter,
    SubmissionRepository,
)
from argumenta.domain.errors import ChapterNotFoundError, WordCountOutOfRangeError
from argumenta.domain.submission import (
    DAILY_SUBMISSION_LIMIT,
    count_words,
    submission_context_for,
)


@dataclass(frozen=True)
class SubmitArgument:
    user_id: uuid.UUID
    chapter_id: uuid.UUID
    body: str
    typing_ms: int | None = None
    paste_count: int = 0


class SubmitArgumentUseCase:
    """The entry move of the game: gate word count and the daily cap, persist
    the submission as evaluating and hand it to the evaluator. The correction
    itself runs out of band (EvaluateSubmissionUseCase), because it takes
    longer than any HTTP timeout in front of us (issue #68)."""

    def __init__(
        self,
        contexts: EvaluationContextRepository,
        submissions: SubmissionRepository,
        progress: ProgressWriter,
        activity: DailyActivityWriter,
        dispatcher: EvaluationDispatcher,
    ) -> None:
        self._contexts = contexts
        self._submissions = submissions
        self._progress = progress
        self._activity = activity
        self._dispatcher = dispatcher

    def execute(self, request: SubmitArgument) -> PendingSubmission:
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

        # atomic gate BEFORE anything is handed off; rolls back with the
        # request transaction if the hand-off fails
        now = datetime.now(tz=UTC)
        self._activity.register_submission(request.user_id, now.date(), DAILY_SUBMISSION_LIMIT)

        pending = self._submissions.create_pending(
            NewSubmission(
                user_id=request.user_id,
                chapter_id=request.chapter_id,
                context=submission_context,
                body=request.body,
                word_count=word_count,
                typing_ms=request.typing_ms,
                paste_count=request.paste_count,
            )
        )
        self._dispatcher.dispatch(pending.submission_id)
        return pending
