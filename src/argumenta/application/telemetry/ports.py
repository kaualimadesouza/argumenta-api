import uuid
from collections.abc import Collection, Sequence
from typing import Protocol

from argumenta.domain.telemetry import SubmissionOwnership, TelemetryRecord


class TelemetryRepository(Protocol):
    def classify_submissions(
        self, user_id: uuid.UUID, submission_ids: Collection[uuid.UUID]
    ) -> SubmissionOwnership:
        """Which of those submissions are the user's, and which of those they
        soft deleted, in one query. Reads deleted rows on purpose."""
        ...

    def store(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> None:
        """Writes the whole batch at once. How few statements that is belongs to
        the adapter; this is the highest volume endpoint in the product."""
        ...
