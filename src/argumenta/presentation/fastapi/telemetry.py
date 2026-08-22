import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from argumenta.application.telemetry.use_cases import RecordTelemetryEventsUseCase
from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.telemetry import (
    MAX_KEYSTROKES,
    MAX_PASTE_CHARS,
    MAX_PASTE_WORDS,
    MAX_SCREEN_LENGTH,
    MAX_TYPING_MS,
    SCREEN_PATTERN,
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


class _EventFields(BaseModel):
    """No unknown fields, and every field bounded: an extra key is exactly where
    the student's text would arrive, and this is the only body in the product a
    client sends unprompted."""

    model_config = ConfigDict(extra="forbid")

    occurred_at: AwareDatetime
    """When it happened on the client, offset required. A naive timestamp is a
    client bug (it would be read in the server timezone), and without any the
    batch only carries flush time, so rhythm stops being reconstructable."""
    submission_id: uuid.UUID | None = None


class PasteEventRequest(_EventFields):
    event_type: Literal[TelemetryEventType.PASTE]
    chars: int = Field(ge=1, le=MAX_PASTE_CHARS)
    words: int | None = Field(default=None, ge=0, le=MAX_PASTE_WORDS)

    def payload(self) -> TelemetryPayload:
        return Paste(chars=self.chars, words=self.words)


class TypingStatsEventRequest(_EventFields):
    event_type: Literal[TelemetryEventType.TYPING_STATS]
    ms: int = Field(ge=0, le=MAX_TYPING_MS)
    keystrokes: int = Field(ge=0, le=MAX_KEYSTROKES)
    backspaces: int | None = Field(default=None, ge=0, le=MAX_KEYSTROKES)

    def payload(self) -> TelemetryPayload:
        return TypingStats(ms=self.ms, keystrokes=self.keystrokes, backspaces=self.backspaces)


class ScreenViewEventRequest(_EventFields):
    event_type: Literal[TelemetryEventType.SCREEN_VIEW]
    screen: str = Field(min_length=1, max_length=MAX_SCREEN_LENGTH, pattern=SCREEN_PATTERN)

    def payload(self) -> TelemetryPayload:
        return ScreenView(screen=self.screen)


TelemetryEventRequest = Annotated[
    PasteEventRequest | TypingStatsEventRequest | ScreenViewEventRequest,
    Field(discriminator="event_type"),
]


class TelemetryBatchRequest(BaseModel):
    events: list[TelemetryEventRequest]


class TelemetryBatchResponse(BaseModel):
    recorded: int
    dropped: int = Field(
        description=(
            "events thrown away because their client date cannot be a clock error; "
            "resending them will not change the answer"
        )
    )


@router.post(
    "/events",
    status_code=201,
    responses={
        413: {"description": "batch over the limit, or a body over the global cap"},
        429: {"description": "too many batches for this student"},
    },
)
def record_events(
    request: TelemetryBatchRequest,
    user_id: CurrentUserId,
    use_case: TelemetryUseCase,
) -> TelemetryBatchResponse:
    """Anti-cheat collection, stored and never blocking: nothing reported here
    changes the student's submission or their grade (PRD decision 12)."""
    batch = use_case.execute(
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
    return TelemetryBatchResponse(recorded=len(batch.records), dropped=batch.dropped)
