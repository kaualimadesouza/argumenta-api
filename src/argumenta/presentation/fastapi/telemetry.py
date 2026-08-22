import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from argumenta.application.telemetry.use_cases import RecordTelemetryEventsUseCase
from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.telemetry import TelemetryRecord
from argumenta.presentation.fastapi.dependencies import (
    CurrentUserId,
    get_record_telemetry_use_case,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

TelemetryUseCase = Annotated[RecordTelemetryEventsUseCase, Depends(get_record_telemetry_use_case)]


class TelemetryEventRequest(BaseModel):
    event_type: TelemetryEventType
    submission_id: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    """Shape depends on the event type: chars pasted, keystrokes and elapsed
    time, screen name. Never the student's text."""


class TelemetryBatchRequest(BaseModel):
    events: list[TelemetryEventRequest]
    """How many events fit in a batch, and how big a payload may be, are rules
    in the domain: repeating them here would only make them unreachable."""


class TelemetryBatchResponse(BaseModel):
    recorded: int


@router.post("/events", status_code=202, response_model=TelemetryBatchResponse)
def record_events(
    request: TelemetryBatchRequest,
    user_id: CurrentUserId,
    use_case: TelemetryUseCase,
) -> TelemetryBatchResponse:
    """Anti-cheat collection, accepted and stored, never blocking: the student's
    submission is not affected by what is reported here (PRD decision 12)."""
    recorded = use_case.execute(
        user_id,
        [
            TelemetryRecord(
                event_type=event.event_type,
                submission_id=event.submission_id,
                payload=event.payload,
            )
            for event in request.events
        ],
    )
    return TelemetryBatchResponse(recorded=recorded)
