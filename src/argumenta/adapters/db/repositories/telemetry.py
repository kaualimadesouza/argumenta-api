import uuid
from collections.abc import Collection, Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Submission, TelemetryEvent
from argumenta.domain.telemetry import SubmissionOwnership, TelemetryRecord


class SqlAlchemyTelemetryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def classify_submissions(
        self, user_id: uuid.UUID, submission_ids: Collection[uuid.UUID]
    ) -> SubmissionOwnership:
        rows = self._session.execute(
            select(Submission.id, Submission.deleted_at).where(
                Submission.id.in_(submission_ids), Submission.user_id == user_id
            )
        ).all()
        return SubmissionOwnership(
            owned=frozenset(row.id for row in rows),
            retired=frozenset(row.id for row in rows if row.deleted_at is not None),
        )

    def store(self, user_id: uuid.UUID, records: Sequence[TelemetryRecord]) -> None:
        """SQLAlchemy batches these ORM objects into a single INSERT, so fifty
        buffered events are one round trip on the busiest endpoint."""
        self._session.add_all(
            [
                TelemetryEvent(
                    user_id=user_id,
                    submission_id=record.submission_id,
                    event_type=record.event_type,
                    occurred_at=record.occurred_at,
                    payload=_payload_of(record),
                )
                for record in records
            ]
        )
        self._session.flush()


def _payload_of(record: TelemetryRecord) -> dict[str, Any]:
    """The jsonb value: a dict here is the column's own shape, not a record
    crossing a boundary. Absent optional fields stay absent instead of becoming
    a row of nulls."""
    return {key: value for key, value in asdict(record.payload).items() if value is not None}
