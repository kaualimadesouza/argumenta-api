"""Anti-cheat telemetry (PRD decision 12): collection only, nothing punitive.
The numbers a client may report are declared here; the boundary enforces them,
because that is where an event turns from JSON into one of these types."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar

from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.errors import TelemetryBatchTooLargeError

MAX_EVENTS_PER_BATCH = 100
"""Per request. The client buffers and flushes; a bigger batch is a bug or an
abuse, and either way it does not belong in one transaction."""

MAX_CLOCK_DRIFT = timedelta(days=365)
"""Sanity bound, not a tolerance: a device clock is off by minutes all the time,
and typing rhythm is read from intervals inside a batch, where a constant offset
cancels out. Only a date that cannot be a clock error is dropped."""

MAX_PASTE_CHARS = 100_000
MAX_PASTE_WORDS = 20_000
MAX_TYPING_MS = 86_400_000
MAX_KEYSTROKES = 1_000_000
MAX_SCREEN_LENGTH = 40
SCREEN_PATTERN = r"^[a-z0-9][a-z0-9_/-]*$"
"""A slug, not a label: bounded and unable to carry prose. This is the only
string a client can put in the payload, so it is the one that has to be tight."""


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
    """Client time, always with an offset. The server also stores its own
    `created_at`, which is flush time: the pair is what tells a slow writer
    from a paste even when the device clock is wrong."""
    submission_id: uuid.UUID | None = None

    @property
    def event_type(self) -> TelemetryEventType:
        """Derived from the payload, so an event cannot claim one type and carry
        the fields of another."""
        return self.payload.event_type


@dataclass(frozen=True)
class SubmissionOwnership:
    """What the caller may point telemetry at."""

    owned: frozenset[uuid.UUID]
    retired: frozenset[uuid.UUID]
    """The soft deleted ones, a subset of `owned`: the event is kept without the
    reference, since the client cannot know and losing the batch would punish
    them for a submission they deleted themselves."""


@dataclass(frozen=True)
class RecordableBatch:
    records: tuple[TelemetryRecord, ...]
    dropped: int
    """Events whose date cannot be a clock error. Dropped one by one, never as a
    batch: a device that is off keeps being off, so refusing the buffer would
    lose every event that phone will ever send."""


def recordable(records: tuple[TelemetryRecord, ...], now: datetime) -> RecordableBatch:
    """Refuses a batch too long for one transaction, and filters the events
    whose client date is nonsense rather than skew."""
    if len(records) > MAX_EVENTS_PER_BATCH:
        raise TelemetryBatchTooLargeError(
            f"{len(records)} events in one batch, limit is {MAX_EVENTS_PER_BATCH}"
        )
    kept = tuple(record for record in records if abs(record.occurred_at - now) <= MAX_CLOCK_DRIFT)
    return RecordableBatch(records=kept, dropped=len(records) - len(kept))
