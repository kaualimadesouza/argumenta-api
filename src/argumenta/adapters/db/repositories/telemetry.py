import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Submission, TelemetryEvent
from argumenta.domain.telemetry import TelemetryRecord


class SqlAlchemyTelemetryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def owned_submission_ids(
        self, user_id: uuid.UUID, submission_ids: Collection[uuid.UUID]
    ) -> set[uuid.UUID]:
        rows = self._session.scalars(
            select(Submission.id).where(
                Submission.id.in_(submission_ids),
                Submission.user_id == user_id,
                Submission.deleted_at.is_(None),
            )
        )
        return set(rows)

    def store(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> int:
        """One multi-row INSERT: fifty buffered events are one round trip."""
        self._session.execute(
            insert(TelemetryEvent).values(
                [
                    {
                        "user_id": user_id,
                        "submission_id": record.submission_id,
                        "event_type": record.event_type.value,
                        "payload": dict(record.payload),
                    }
                    for record in records
                ]
            )
        )
        self._session.flush()
        return len(records)
