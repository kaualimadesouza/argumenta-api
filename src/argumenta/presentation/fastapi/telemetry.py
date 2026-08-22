import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from argumenta.application.telemetry.use_cases import RecordTelemetryEventsUseCase
from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.telemetry import (
    MAX_EVENTS_PER_BATCH,
    Paste,
    ScreenView,
    TelemetryPayload,
    TelemetryRecord,
    TypingStats,
)
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_record_telemetry_use_case,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

TelemetryUseCase = Annotated[RecordTelemetryEventsUseCase, Depends(get_record_telemetry_use_case)]

TRANSPORT_MAX_EVENTS = 10 * MAX_EVENTS_PER_BATCH
"""Transport bound, an order of magnitude above the product rule, so a body
that is absurd is refused before it is turned into objects. How many events
belong in one batch stays a rule in the domain, and stays reachable."""


class _EventFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """No unknown fields: the payload of an event is a shape this system knows,
    and an extra key is exactly where the student's text would arrive."""

    occurred_at: datetime
    """When it happened on the client. Required: without it the batch only
    carries flush time, and typing rhythm stops being reconstructable."""
    submission_id: uuid.UUID | None = None


class PasteEventRequest(_EventFields):
    event_type: Literal[TelemetryEventType.PASTE]
    chars: int = Field(ge=1, le=100_000)
    words: int | None = Field(default=None, ge=0, le=20_000)

    def payload(self) -> TelemetryPayload:
        return Paste(chars=self.chars, words=self.words)


class TypingStatsEventRequest(_EventFields):
    event_type: Literal[TelemetryEventType.TYPING_STATS]
    ms: int = Field(ge=0, le=86_400_000)
    keystrokes: int = Field(ge=0, le=1_000_000)
    backspaces: int | None = Field(default=None, ge=0, le=1_000_000)

    def payload(self) -> TelemetryPayload:
        return TypingStats(ms=self.ms, keystrokes=self.keystrokes, backspaces=self.backspaces)


class ScreenViewEventRequest(_EventFields):
    event_type: Literal[TelemetryEventType.SCREEN_VIEW]
    screen: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9_/-]*$")
    """A slug, not a label: bounded and unable to carry prose."""

    def payload(self) -> TelemetryPayload:
        return ScreenView(screen=self.screen)


TelemetryEventRequest = Annotated[
    PasteEventRequest | TypingStatsEventRequest | ScreenViewEventRequest,
    Field(discriminator="event_type"),
]


class TelemetryBatchRequest(BaseModel):
    events: list[TelemetryEventRequest] = Field(max_length=TRANSPORT_MAX_EVENTS)


class TelemetryBatchResponse(BaseModel):
    recorded: int


@router.post("/events", status_code=201)
def record_events(
    request: TelemetryBatchRequest,
    user_id: CurrentUserId,
    use_case: TelemetryUseCase,
) -> TelemetryBatchResponse:
    """Anti-cheat collection, stored and never blocking: nothing reported here
    changes the student's submission or their grade (PRD decision 12)."""
    recorded = use_case.execute(
        user_id,
        [
            TelemetryRecord(
                payload=event.payload(),
                occurred_at=event.occurred_at,
                submission_id=event.submission_id,
            )
            for event in request.events
        ],
    )
    return TelemetryBatchResponse(recorded=recorded)
