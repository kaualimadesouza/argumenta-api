import uuid
from collections.abc import Collection, Sequence
from typing import Protocol

from argumenta.domain.telemetry import TelemetryRecord


class TelemetryRepository(Protocol):
    def owned_submission_ids(
        self, user_id: uuid.UUID, submission_ids: Collection[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Which of those submissions belong to this user, in one query."""
        ...

    def store(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> int:
        """Writes the whole batch as one statement and returns how many rows
        landed: this is the highest volume endpoint in the product."""
        ...
