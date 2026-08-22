"""Issue #13: anti-cheat telemetry, tests first (TDD). Collection only: nothing
punishes a student, and nothing a student reports can hurt the product."""

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import Submission, TelemetryEvent
from argumenta.adapters.security.rate_limiter import SlidingWindowRateLimiter
from argumenta.domain.errors import TelemetryBatchTooLargeError
from argumenta.domain.telemetry import (
    MAX_CLOCK_DRIFT,
    MAX_EVENTS_PER_BATCH,
    Paste,
    TelemetryRecord,
    recordable,
)
from argumenta.presentation.fastapi.dependencies import get_telemetry_rate_limiter
from tests.conftest import ScriptedEngine, submit_text

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
NUL = "\u0000"
"""jsonb cannot store it, so no field may accept it."""


def _record(occurred_at: datetime = NOW) -> TelemetryRecord:
    return TelemetryRecord(payload=Paste(chars=120), occurred_at=occurred_at)


def _event(event_type: str = "paste", **fields: Any) -> dict[str, Any]:
    payloads: dict[str, dict[str, Any]] = {
        "paste": {"chars": 240, "words": 40},
        "typing_stats": {"ms": 90000, "keystrokes": 620},
        "screen_view": {"screen": "chapter"},
    }
    return {
        "event_type": event_type,
        "occurred_at": datetime.now(tz=UTC).isoformat(),
        **payloads[event_type],
        **fields,
    }


class TestBatchRule:
    def test_the_product_rules_are_these_numbers(self) -> None:
        """Pinned, not derived: every test below builds its input from these
        constants, so all of them stay green if the rule is loosened."""
        assert MAX_EVENTS_PER_BATCH == 100
        assert timedelta(days=365) == MAX_CLOCK_DRIFT

    def test_a_batch_at_the_limit_is_accepted(self) -> None:
        batch = recordable(tuple(_record() for _ in range(100)), NOW)

        assert (len(batch.records), batch.dropped) == (100, 0)

    def test_a_batch_over_the_limit_is_refused(self) -> None:
        with pytest.raises(TelemetryBatchTooLargeError):
            recordable(tuple(_record() for _ in range(101)), NOW)

    def test_a_clock_that_runs_fast_is_kept(self) -> None:
        """A phone six minutes ahead is normal, and rhythm is read from the
        intervals inside a batch, where a constant offset cancels out."""
        batch = recordable((_record(NOW + timedelta(minutes=6)),), NOW)

        assert (len(batch.records), batch.dropped) == (1, 0)

    def test_an_impossible_date_is_dropped_alone(self) -> None:
        """One event of nonsense must not cost the buffer: a device whose clock
        is wrong keeps being wrong, so refusing the batch loses every event it
        will ever send."""
        batch = recordable((_record(datetime(1999, 1, 1, tzinfo=UTC)), _record()), NOW)

        assert (len(batch.records), batch.dropped) == (1, 1)

    def test_the_event_type_comes_from_the_payload(self) -> None:
        """So an event cannot claim one type and carry the fields of another."""
        assert _record().event_type == "paste"


class TestTelemetryEndpoint:
    def test_a_batch_of_known_events_is_recorded(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={"events": [_event("paste"), _event("typing_stats"), _event("screen_view")]},
        )

        assert response.status_code == 201, response.text
        assert response.json() == {"recorded": 3, "dropped": 0}
        with Session(db_engine) as session:
            stored = session.scalars(select(TelemetryEvent).order_by(TelemetryEvent.id)).all()
        assert [row.event_type for row in stored] == ["paste", "typing_stats", "screen_view"]
        assert stored[0].payload == {"chars": 240, "words": 40}
        assert stored[1].payload == {"ms": 90000, "keystrokes": 620}
        assert all(row.submission_id is None for row in stored)

    def test_client_time_survives_the_flush(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """Typing rhythm is a time series: the server only knows when the buffer
        was flushed, so the client time is what makes the events readable."""
        client, _ = game
        moments = [
            (datetime.now(tz=UTC) - timedelta(seconds=seconds)).replace(microsecond=0)
            for seconds in (30, 20, 10)
        ]

        response = client.post(
            "/telemetry/events",
            json={
                "events": [
                    _event("typing_stats", occurred_at=moment.isoformat()) for moment in moments
                ]
            },
        )

        assert response.status_code == 201, response.text
        with Session(db_engine) as session:
            stored = session.scalars(select(TelemetryEvent).order_by(TelemetryEvent.id)).all()
        assert [row.occurred_at for row in stored] == moments
        assert len({row.created_at for row in stored}) == 1, "one flush, three moments"

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
            json={"events": [_event("paste", submission_id=submission_id)]},
        )

        assert response.status_code == 201, response.text
        with Session(db_engine) as session:
            stored = session.scalars(select(TelemetryEvent)).one()
        assert str(stored.submission_id) == submission_id

    def test_an_unknown_event_type_is_refused(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={
                "events": [{"event_type": "keylog", "occurred_at": NOW.isoformat(), "keys": "abc"}]
            },
        )

        assert response.status_code == 422
        assert _rows(db_engine) == []

    def test_a_payload_cannot_smuggle_the_students_text(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """The whole point of typed payloads: a paste event is a count, and
        there is no field for prose to arrive in."""
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={"events": [_event("paste", text="a redacao inteira do aluno " * 40)]},
        )

        assert response.status_code == 422
        assert _rows(db_engine) == []

    def test_a_null_byte_cannot_reach_postgres(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """jsonb cannot store U+0000 and clipboard text carries it, so an
        unbounded string field would be a 500 the client could not escape. The
        only string left is a slug, and the slug pattern refuses it."""
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={"events": [_event("screen_view", screen=f"chap{NUL}ter")]},
        )

        assert response.status_code == 422
        assert _rows(db_engine) == []

    def test_a_body_too_big_is_refused_before_it_is_parsed(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """Rejecting a 60 MB batch by deserializing it first costs hundreds of
        megabytes of RSS, and the worker that dies takes corrections with it."""
        client, _ = game
        events = [_event("screen_view") for _ in range(30_000)]

        response = client.post("/telemetry/events", json={"events": events})

        assert response.status_code == 413
        assert response.json()["detail"] == "RequestTooLarge"
        assert _rows(db_engine) == []

    def test_a_naive_timestamp_is_a_client_bug_not_a_guess(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """Without an offset the server would read it in its own timezone. A
        shape error is deterministic, so the client dev sees it in development;
        a wrong clock is not, which is why that one is tolerated instead."""
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={"events": [_event("paste", occurred_at="2026-08-22T12:00:00")]},
        )

        assert response.status_code == 422
        assert _rows(db_engine) == []

    def test_an_impossible_date_does_not_cost_the_rest_of_the_buffer(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post(
            "/telemetry/events",
            json={
                "events": [
                    _event("paste", occurred_at="1999-01-01T00:00:00+00:00"),
                    _event("typing_stats"),
                ]
            },
        )

        assert response.status_code == 201, response.text
        assert response.json() == {"recorded": 1, "dropped": 1}
        assert [row.event_type for row in _rows(db_engine)] == ["typing_stats"]

    def test_a_chunked_body_is_counted_as_it_arrives(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """Content-Length is a hint a client may not send at all: a streamed
        body declares nothing, and the parser materializes it before validation
        or auth, so the bytes have to be counted while they arrive."""
        client, _ = game
        payload = json.dumps({"events": [_event("screen_view") for _ in range(30_000)]}).encode()

        def chunks() -> Iterator[bytes]:
            for start in range(0, len(payload), 64_000):
                yield payload[start : start + 64_000]

        response = client.post(
            "/telemetry/events",
            content=chunks(),
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 413
        assert response.json()["detail"] == "RequestTooLarge"
        assert _rows(db_engine) == []

    def test_an_oversized_batch_is_refused_by_the_domain_rule(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """The product cap lives in the domain, so the endpoint answers with it
        instead of a schema error the rule would never reach."""
        client, _ = game
        events = [_event("paste") for _ in range(MAX_EVENTS_PER_BATCH + 1)]

        response = client.post("/telemetry/events", json={"events": events})

        assert response.status_code == 413
        assert response.json()["detail"] == "TelemetryBatchTooLargeError"
        assert _rows(db_engine) == []

    def test_an_empty_flush_is_a_no_op_not_an_error(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game

        response = client.post("/telemetry/events", json={"events": []})

        assert response.status_code == 201
        assert response.json() == {"recorded": 0, "dropped": 0}
        assert _rows(db_engine) == []

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
            json={"events": [_event("paste"), _event("paste", submission_id=submission_id)]},
        )

        assert response.status_code == 404
        assert _rows(db_engine) == [], "a rejected batch is all or nothing"

    def test_a_deleted_submission_of_their_own_does_not_lose_the_batch(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        """The client cannot know the submission was retired. Refusing the whole
        buffer over a stale reference would be telemetry punishing a student."""
        client, chapter_id = game
        submission_id = submit_text(client, chapter_id).json()["submission_id"]
        with Session(db_engine) as session:
            submission = session.get(Submission, uuid.UUID(submission_id))
            assert submission is not None
            submission.deleted_at = datetime.now(tz=UTC)
            session.commit()

        response = client.post(
            "/telemetry/events",
            json={"events": [_event("paste", submission_id=submission_id)]},
        )

        assert response.status_code == 201, response.text
        with Session(db_engine) as session:
            stored = session.scalars(select(TelemetryEvent)).one()
        assert stored.submission_id is None

    def test_the_whole_batch_is_one_insert(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        """This endpoint is the highest volume one in the product: fifty events
        must not be fifty round trips."""
        client, _ = game
        events = [_event("screen_view", screen=f"tela-{index}") for index in range(50)]

        with _telemetry_inserts(db_engine) as statements:
            response = client.post("/telemetry/events", json={"events": events})

        assert response.json() == {"recorded": 50, "dropped": 0}
        assert len(statements) == 1, f"{len(statements)} INSERTs for one batch"

    def test_a_student_cannot_flood_the_only_unbounded_write_they_have(
        self, app: FastAPI, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game
        limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60)
        app.dependency_overrides[get_telemetry_rate_limiter] = lambda: limiter

        first = client.post("/telemetry/events", json={"events": [_event("paste")]})
        second = client.post("/telemetry/events", json={"events": [_event("paste")]})

        assert first.status_code == 201
        assert second.status_code == 429
        assert len(_rows(db_engine)) == 1

    def test_an_empty_flush_still_spends_a_rate_limit_slot(
        self, app: FastAPI, game: tuple[TestClient, uuid.UUID]
    ) -> None:
        """Otherwise an empty body is a free request forever."""
        client, _ = game
        limiter = SlidingWindowRateLimiter(max_attempts=1, window_seconds=60)
        app.dependency_overrides[get_telemetry_rate_limiter] = lambda: limiter

        first = client.post("/telemetry/events", json={"events": []})
        second = client.post("/telemetry/events", json={"events": []})

        assert (first.status_code, second.status_code) == (201, 429)

    def test_telemetry_requires_a_logged_in_student(self, client: TestClient) -> None:
        response = client.post("/telemetry/events", json={"events": [_event("paste")]})

        assert response.status_code == 401


class TestGlobalBodyCap:
    """The cap arrived with telemetry but governs every route, so the routes
    that already took a big body have to say what happens now."""

    def test_a_draft_over_the_cap_is_refused(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, chapter_id = game

        response = client.put(f"/chapters/{chapter_id}/draft", json={"body": "a" * 1_100_000})

        assert response.status_code == 413
        assert response.json()["detail"] == "RequestTooLarge"

    def test_a_draft_under_the_cap_still_saves(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, chapter_id = game

        response = client.put(f"/chapters/{chapter_id}/draft", json={"body": "a" * 5_000})

        assert response.status_code == 204


def _rows(db_engine: Engine) -> list[TelemetryEvent]:
    with Session(db_engine) as session:
        return list(session.scalars(select(TelemetryEvent)).all())


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
