import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

from argumenta.application.ports import RateLimiter
from argumenta.application.telemetry.ports import TelemetryRepository
from argumenta.domain.errors import SubmissionNotFoundError, TooManyAttemptsError
from argumenta.domain.telemetry import RecordableBatch, TelemetryRecord, recordable


class RecordTelemetryEventsUseCase:
    """Records a batch of client events. Collection only: nothing here changes
    what the student can do (PRD decision 12), and the only write it refuses
    outright is one pointing at somebody else's submission."""

    def __init__(self, events: TelemetryRepository, limiter: RateLimiter) -> None:
        self._events = events
        self._limiter = limiter

    def execute(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> RecordableBatch:
        """Returns what was filed and what was thrown away, so the client can
        stop resending a buffer the server will never keep."""
        if not self._limiter.check(f"telemetry:{user_id}"):
            raise TooManyAttemptsError("too many telemetry batches, slow down")
        batch = recordable(tuple(records), datetime.now(tz=UTC))
        if not batch.records:
            return batch
        stored = self._attach_owned_submissions(user_id, batch.records)
        self._events.store(user_id, stored)
        return RecordableBatch(records=stored, dropped=batch.dropped)

    def _attach_owned_submissions(
        self, user_id: uuid.UUID, batch: tuple[TelemetryRecord, ...]
    ) -> tuple[TelemetryRecord, ...]:
        """A reference to a submission that is not the user's refuses the whole
        batch; one to a submission of theirs that was deleted loses the
        reference, and the event is still recorded."""
        referenced = {record.submission_id for record in batch if record.submission_id is not None}
        if not referenced:
            return batch
        ownership = self._events.classify_submissions(user_id, referenced)
        unknown = referenced - ownership.owned
        if unknown:
            raise SubmissionNotFoundError(
                "telemetry pointed at a submission that is not this user's"
            )
        if not ownership.retired:
            return batch
        return tuple(
            replace(record, submission_id=None)
            if record.submission_id in ownership.retired
            else record
            for record in batch
        )
