"""Issue #13: anti-cheat telemetry without blocking anything, tests first (TDD).

The PRD decision is collection only: nothing here punishes a student, and the
endpoint exists so a future decision has data instead of opinions.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.base import Base
from argumenta.adapters.db.models import TelemetryEvent
from argumenta.domain.enums import TelemetryEventType
from argumenta.domain.errors import (
    EmptyTelemetryBatchError,
    TelemetryBatchTooLargeError,
    TelemetryPayloadTooLargeError,
)
from argumenta.domain.telemetry import (
    MAX_EVENTS_PER_BATCH,
    MAX_PAYLOAD_CHARS,
    TelemetryRecord,
    ensure_batch_is_recordable,
)
from tests.conftest import ScriptedEngine, submit_text


def _record(
    event_type: TelemetryEventType = TelemetryEventType.PASTE,
    payload: dict[str, Any] | None = None,
) -> TelemetryRecord:
    return TelemetryRecord(
        event_type=event_type,
        submission_id=None,
        payload=payload if payload is not None else {"chars": 120},
    )


class TestBatchRule:
    def test_an_empty_batch_is_refused(self) -> None:
        with pytest.raises(EmptyTelemetryBatchError):
            ensure_batch_is_recordable(())

    def test_a_batch_at_the_limit_is_accepted(self) -> None:
        ensure_batch_is_recordable(tuple(_record() for _ in range(MAX_EVENTS_PER_BATCH)))

    def test_a_batch_over_the_limit_is_refused(self) -> None:
        with pytest.raises(TelemetryBatchTooLargeError):
            ensure_batch_is_recordable(tuple(_record() for _ in range(MAX_EVENTS_PER_BATCH + 1)))

    def test_an_oversized_payload_is_refused(self) -> None:
        """One jsonb column in the whole model is not a place to dump a text."""
        with pytest.raises(TelemetryPayloadTooLargeError):
            ensure_batch_is_recordable((_record(payload={"text": "x" * MAX_PAYLOAD_CHARS}),))


class TestTelemetryEndpoint:
    def test_a_batch_of_known_events_is_recorded(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={
                "events": [
                    {"event_type": "paste", "payload": {"chars": 240, "source": "clipboard"}},
                    {"event_type": "typing_stats", "payload": {"ms": 90000, "keystrokes": 620}},
                    {"event_type": "screen_view", "payload": {"screen": "chapter"}},
                ]
            },
        )

        assert response.status_code == 202, response.text
        assert response.json() == {"recorded": 3}
        with Session(db_engine) as session:
            stored = session.scalars(select(TelemetryEvent).order_by(TelemetryEvent.id)).all()
        assert [row.event_type for row in stored] == ["paste", "typing_stats", "screen_view"]
        assert stored[0].payload == {"chars": 240, "source": "clipboard"}
        assert all(row.submission_id is None for row in stored)

    def test_an_event_can_point_at_the_students_own_submission(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        submission_id = submit_text(client, chapter_id).json()["submission_id"]

        response = client.post(
            "/telemetry/events",
            json={
                "events": [
                    {
                        "event_type": "paste",
                        "submission_id": submission_id,
                        "payload": {"chars": 40},
                    }
                ]
            },
        )

        assert response.status_code == 202, response.text
        with Session(db_engine) as session:
            stored = session.scalars(select(TelemetryEvent)).one()
        assert str(stored.submission_id) == submission_id

    def test_an_unknown_event_type_is_refused(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={"events": [{"event_type": "keylog", "payload": {}}]},
        )

        assert response.status_code == 422
        with Session(db_engine) as session:
            assert session.scalars(select(TelemetryEvent)).all() == []

    def test_someone_elses_submission_records_nothing(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        """Telemetry is collection, not a way to write into another student's
        history."""
        client, chapter_id = game
        submission_id = submit_text(client, chapter_id).json()["submission_id"]
        client.post("/auth/logout")
        assert (
            client.post(
                "/auth/register",
                json={
                    "email": "outra@example.com",
                    "nickname": "Outra",
                    "password": "correct-horse-9",  # pragma: allowlist secret
                    "accepted_terms": True,
                },
            ).status_code
            == 201
        )

        response = client.post(
            "/telemetry/events",
            json={
                "events": [
                    {"event_type": "paste", "payload": {"chars": 1}},
                    {
                        "event_type": "paste",
                        "submission_id": submission_id,
                        "payload": {"chars": 2},
                    },
                ]
            },
        )

        assert response.status_code == 404
        with Session(db_engine) as session:
            assert session.scalars(select(TelemetryEvent)).all() == [], (
                "a rejected batch is all or nothing"
            )

    def test_the_whole_batch_is_one_insert(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """This endpoint is the highest volume one in the product: fifty events
        must not be fifty round trips."""
        client, _ = game
        events = [
            {"event_type": "screen_view", "payload": {"screen": f"tela-{index}"}}
            for index in range(50)
        ]

        with _telemetry_inserts(db_engine) as statements:
            response = client.post("/telemetry/events", json={"events": events})

        assert response.json() == {"recorded": 50}
        assert len(statements) == 1, f"{len(statements)} INSERTs for one batch"

    def test_an_oversized_batch_is_refused_by_the_domain_rule(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """The cap lives in the domain, so the endpoint answers with it instead
        of a schema error that the rule would never reach."""
        client, _ = game
        events = [
            {"event_type": "paste", "payload": {"chars": index}}
            for index in range(MAX_EVENTS_PER_BATCH + 1)
        ]

        response = client.post("/telemetry/events", json={"events": events})

        assert response.status_code == 413
        assert response.json()["detail"] == "TelemetryBatchTooLargeError"
        with Session(db_engine) as session:
            assert session.scalars(select(TelemetryEvent)).all() == []

    def test_an_empty_batch_is_refused(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, _ = game

        response = client.post("/telemetry/events", json={"events": []})

        assert response.status_code == 422
        assert response.json()["detail"] == "EmptyTelemetryBatchError"

    def test_a_payload_carrying_the_students_text_is_refused(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={
                "events": [
                    {"event_type": "paste", "payload": {"text": "x" * (MAX_PAYLOAD_CHARS + 1)}}
                ]
            },
        )

        assert response.status_code == 413
        with Session(db_engine) as session:
            assert session.scalars(select(TelemetryEvent)).all() == []

    def test_telemetry_requires_a_logged_in_student(self, client: TestClient) -> None:
        response = client.post(
            "/telemetry/events", json={"events": [{"event_type": "paste", "payload": {}}]}
        )

        assert response.status_code == 401


def test_the_events_are_indexed_by_user_and_time() -> None:
    """The acceptance criterion of the card: the anti-cheat question is always
    "this student, this period"."""
    table = Base.metadata.tables["telemetry_events"]
    index = next(
        index for index in table.indexes if index.name == "ix_telemetry_events_user_created"
    )

    assert [column.name for column in index.columns] == ["user_id", "created_at"]


@contextmanager
def _telemetry_inserts(engine: Engine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        if "INSERT INTO telemetry_events" in statement:
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record)
