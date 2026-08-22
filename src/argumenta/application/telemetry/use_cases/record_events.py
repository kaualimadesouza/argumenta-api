import uuid
from collections.abc import Sequence

from argumenta.application.telemetry.ports import TelemetryRepository
from argumenta.domain.errors import SubmissionNotFoundError
from argumenta.domain.telemetry import TelemetryRecord, ensure_batch_is_recordable


class RecordTelemetryEventsUseCase:
    """Records a batch of client events. Collection only: nothing here changes
    what the student can do (PRD decision 12)."""

    def __init__(self, events: TelemetryRepository) -> None:
        self._events = events

    def execute(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> int:
        ensure_batch_is_recordable(records)
        referenced = {
            record.submission_id for record in records if record.submission_id is not None
        }
        if referenced:
            missing = referenced - self._events.owned_submission_ids(user_id, referenced)
            if missing:
                raise SubmissionNotFoundError(
                    "telemetry pointed at a submission that is not this user's"
                )
        return self._events.store(user_id, records)
