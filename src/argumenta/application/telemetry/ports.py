import uuid
from collections.abc import Collection, Sequence
from typing import Protocol

from argumenta.domain.telemetry import SubmissionOwnership, TelemetryRecord


class TelemetryRepository(Protocol):
    def classify_submissions(
        self, user_id: uuid.UUID, submission_ids: Collection[uuid.UUID]
    ) -> SubmissionOwnership:
        """Which of those submissions are the user's, and which of the user's
        own were soft deleted, in one query."""
        ...

    def store(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> None:
        """Writes the whole batch as one statement: this is the highest volume
        endpoint in the product."""
        ...
