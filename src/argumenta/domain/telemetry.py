"""Anti-cheat telemetry (PRD decision 12): collection only, nothing punitive.
The rules here protect the database and the measurement, not the student."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar

from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.errors import (
    TelemetryBatchTooLargeError,
    TelemetryTimestampError,
)

MAX_EVENTS_PER_BATCH = 100
"""Per request. The client buffers and flushes; a bigger batch is a bug or an
abuse, and either way it does not belong in one transaction."""

MAX_CLOCK_SKEW = timedelta(minutes=5)
"""How far ahead of the server a client clock may be. Beyond that the timestamp
is useless for ordering, and keeping it would poison the only axis that makes
typing rhythm readable."""

MAX_EVENT_AGE = timedelta(days=1)
"""How stale a buffered event may be. A client that was offline for a week is
reporting history nobody will read."""


@dataclass(frozen=True)
class Paste:
    chars: int
    words: int | None = None
    event_type: ClassVar[TelemetryEventType] = TelemetryEventType.PASTE


@dataclass(frozen=True)
class TypingStats:
    ms: int
    keystrokes: int
    backspaces: int | None = None
    event_type: ClassVar[TelemetryEventType] = TelemetryEventType.TYPING_STATS


@dataclass(frozen=True)
class ScreenView:
    screen: str
    event_type: ClassVar[TelemetryEventType] = TelemetryEventType.SCREEN_VIEW


TelemetryPayload = Paste | TypingStats | ScreenView
"""The three known events, as types. An unknown event is not a new column and
not a free-form blob: it is a client bug, refused at the boundary."""


@dataclass(frozen=True)
class TelemetryRecord:
    payload: TelemetryPayload
    occurred_at: datetime
    """Client time. The server also stores its own `created_at`, which is flush
    time: the two together are what tells a slow writer from a paste."""
    submission_id: uuid.UUID | None = None

    @property
    def event_type(self) -> TelemetryEventType:
        """Derived from the payload, so an event cannot claim one type and carry
        the fields of another."""
        return self.payload.event_type


@dataclass(frozen=True)
class SubmissionOwnership:
    """What the caller may point telemetry at."""

    active: frozenset[uuid.UUID]
    retired: frozenset[uuid.UUID]
    """Soft deleted, but theirs: the event is kept without the reference, since
    the client cannot know and losing the batch would punish them."""


def ensure_batch_is_recordable(records: tuple[TelemetryRecord, ...], now: datetime) -> None:
    """Raises when the batch is too long for one transaction, or carries a
    timestamp that cannot be true."""
    if len(records) > MAX_EVENTS_PER_BATCH:
        raise TelemetryBatchTooLargeError(
            f"{len(records)} events in one batch, limit is {MAX_EVENTS_PER_BATCH}"
        )
    for record in records:
        if record.occurred_at > now + MAX_CLOCK_SKEW:
            raise TelemetryTimestampError(f"event dated {record.occurred_at} is in the future")
        if record.occurred_at < now - MAX_EVENT_AGE:
            raise TelemetryTimestampError(f"event dated {record.occurred_at} is too old to file")
