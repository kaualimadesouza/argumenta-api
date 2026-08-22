"""Anti-cheat telemetry: what the product is allowed to collect, and how much.

PRD decision 12 is collection without blocking, so there is no rule here that
punishes a student. The rules that do exist protect the database from a client
that sends too much.
"""

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.errors import (
    EmptyTelemetryBatchError,
    TelemetryBatchTooLargeError,
    TelemetryPayloadTooLargeError,
)

MAX_EVENTS_PER_BATCH = 100
"""Per request. The client buffers and flushes; a bigger batch is a bug or an
abuse, and either way it is not worth a single transaction."""

MAX_PAYLOAD_CHARS = 2000
"""Serialized size of one event payload. The shape of a paste or a typing
snapshot is a handful of numbers: this is the only jsonb in the model and it is
not a place to park the student's text."""


@dataclass(frozen=True)
class TelemetryRecord:
    """One event the client reports. `payload` stays a mapping on purpose: it is
    the jsonb value itself, different per event type, not a record this system
    reads fields out of."""

    event_type: TelemetryEventType
    submission_id: uuid.UUID | None
    payload: Mapping[str, Any]


def ensure_batch_is_recordable(records: Sequence[TelemetryRecord]) -> None:
    """Raises when the batch is empty, too long, or carries a payload too big to
    belong in a telemetry row."""
    if not records:
        raise EmptyTelemetryBatchError("a telemetry batch needs at least one event")
    if len(records) > MAX_EVENTS_PER_BATCH:
        raise TelemetryBatchTooLargeError(
            f"{len(records)} events in one batch, limit is {MAX_EVENTS_PER_BATCH}"
        )
    for record in records:
        size = len(json.dumps(record.payload, ensure_ascii=False))
        if size > MAX_PAYLOAD_CHARS:
            raise TelemetryPayloadTooLargeError(
                f"payload of {size} chars, limit is {MAX_PAYLOAD_CHARS}"
            )
