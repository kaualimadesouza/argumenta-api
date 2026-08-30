import uuid

from argumenta.application.gameplay.ports import DailyActivityWriter, SubmissionRepository
from argumenta.domain.enums import SubmissionStatus


class RecordEvaluationFailureUseCase:
    """Runs in its own transaction after the evaluation blew up: flips the
    submission to failed (recoverable) and refunds the daily tick, so the
    student's 3-a-day budget only pays for corrections that happened."""

    def __init__(self, submissions: SubmissionRepository, activity: DailyActivityWriter) -> None:
        self._submissions = submissions
        self._activity = activity

    def execute(self, submission_id: uuid.UUID) -> None:
        record = self._submissions.get_record(submission_id)
        if record is None or record.status != SubmissionStatus.EVALUATING:
            return
        self._submissions.mark_failed(submission_id)
        self._activity.withdraw_submission(record.user_id, record.submitted_at.date())
