"""Integration tests of POST /chapters/{id}/submissions and the draft autosave,
derived from the acceptance criteria of issue #8. Shared fixtures (game,
engine_double, ScriptedEngine, submit_text) live in conftest.py."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from tests.integration.conftest import ScriptedEngine
from tests.integration.conftest import submit_text as _submit

from argumenta.adapters.db.models import (
    Chapter,
    ChapterProgress,
    DailyActivity,
    Draft,
    Evaluation,
    Submission,
)
from argumenta.domain.enums import ChapterStatus


class TestStateTransitions:
    def test_approved_passes_and_records_the_passing_submission(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, chapter_id = game

        response = _submit(client, chapter_id)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["verdict"] == "approved"
        assert body["chapter_status"] == "passed"
        with Session(db_engine) as session:
            progress = session.scalar(
                select(ChapterProgress).where(ChapterProgress.chapter_id == chapter_id)
            )
            assert progress is not None
            assert progress.status == ChapterStatus.PASSED
            assert progress.passed_at is not None
            assert str(progress.passing_submission_id) == body["submission_id"]

    def test_technical_failure_keeps_drafting(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        engine_double.scripted = "failed_technical"

        body = _submit(client, chapter_id).json()

        assert body["verdict"] == "failed_technical"
        assert body["chapter_status"] == "drafting"
        with Session(db_engine) as session:
            status = session.scalar(
                select(ChapterProgress.status).where(ChapterProgress.chapter_id == chapter_id)
            )
        assert status == ChapterStatus.DRAFTING

    def test_persuasion_failure_opens_the_consequence_branch(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
    ) -> None:
        client, chapter_id = game
        engine_double.scripted = "failed_persuasion"

        body = _submit(client, chapter_id).json()

        assert body["verdict"] == "failed_persuasion"
        assert body["chapter_status"] == "in_consequence"
        # the chapter now serves the consequence script
        assert client.get(f"/chapters/{chapter_id}").json()["branch"] == "consequence"


class TestDailyLimit:
    def test_fourth_submission_of_the_day_is_blocked(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
    ) -> None:
        client, chapter_id = game
        engine_double.scripted = "failed_technical"

        for _ in range(3):
            assert _submit(client, chapter_id).status_code == 201
        blocked = _submit(client, chapter_id)

        assert blocked.status_code == 429

    def test_any_verdict_counts_for_the_streak(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        engine_double.scripted = "failed_technical"

        _submit(client, chapter_id)

        assert client.get("/track").json()["streak_days"] == 1
        with Session(db_engine) as session:
            activity = session.scalars(select(DailyActivity)).one()
        assert activity.submissions_count == 1
        assert activity.approved_count == 0


class TestPersistence:
    def test_ruler_is_frozen_into_the_evaluation(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, chapter_id = game

        _submit(client, chapter_id)

        with Session(db_engine) as session:
            evaluation = session.scalars(select(Evaluation)).one()
        # tutorial ruler at submission time (DER: recalibration never rewrites)
        assert evaluation.floor_value == 40
        assert evaluation.min_average == 50
        assert evaluation.is_current is True
        assert evaluation.model == "claude-sonnet-5"

    def test_attempt_number_increments_per_user_and_chapter(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        engine_double.scripted = "failed_technical"

        first = _submit(client, chapter_id).json()
        second = _submit(client, chapter_id).json()

        assert first["attempt_number"] == 1
        assert second["attempt_number"] == 2
        with Session(db_engine) as session:
            count = len(session.scalars(select(Submission)).all())
        assert count == 2

    def test_word_count_out_of_range_costs_nothing(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game

        response = _submit(client, chapter_id, body="curto demais")

        assert response.status_code == 422
        assert engine_double.calls == []
        with Session(db_engine) as session:
            assert session.scalars(select(Submission)).all() == []
            assert session.scalars(select(DailyActivity)).all() == []

    def test_locked_chapter_rejects_submissions(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game
        with Session(db_engine) as session:
            locked_id = session.scalar(select(Chapter.id).where(Chapter.position == 2))

        assert _submit(client, locked_id).status_code == 409  # type: ignore[arg-type]

    def test_passed_chapter_rejects_resubmission(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, chapter_id = game
        assert _submit(client, chapter_id).status_code == 201

        assert _submit(client, chapter_id).status_code == 409


class TestCorrectionResponse:
    def test_response_carries_the_whole_correction_screen(
        self, game: tuple[TestClient, uuid.UUID]
    ) -> None:
        client, chapter_id = game

        body = _submit(client, chapter_id).json()

        assert {s["dimension"] for s in body["scores"]} == {
            "norma_culta",
            "coesao",
            "coerencia",
            "repertorio",
            "persuasao",
        }
        for score in body["scores"]:
            assert score["evidence"]
            assert score["passed_floor"] is True
        assert body["floor_value"] == 40
        assert body["min_average"] == 50
        assert body["average_score"] == 80
        assert body["annotations"] == []
        assert body["para_passar"] == []


class TestDraftAutosave:
    def test_draft_saves_and_shows_in_the_chapter(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, chapter_id = game

        response = client.put(
            f"/chapters/{chapter_id}/draft", json={"body": "rascunho em progresso"}
        )

        assert response.status_code == 204
        assert client.get(f"/chapters/{chapter_id}").json()["draft_body"] == (
            "rascunho em progresso"
        )

    def test_draft_upsert_overwrites(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, chapter_id = game
        client.put(f"/chapters/{chapter_id}/draft", json={"body": "v1"})
        client.put(f"/chapters/{chapter_id}/draft", json={"body": "v2"})

        assert client.get(f"/chapters/{chapter_id}").json()["draft_body"] == "v2"

    def test_approval_discards_the_draft(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, chapter_id = game
        client.put(f"/chapters/{chapter_id}/draft", json={"body": "quase la"})

        assert _submit(client, chapter_id).status_code == 201

        with Session(db_engine) as session:
            draft = session.scalars(select(Draft)).one()
        assert draft.deleted_at is not None

    def test_locked_chapter_rejects_drafts(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, _ = game
        with Session(db_engine) as session:
            locked_id = session.scalar(select(Chapter.id).where(Chapter.position == 2))

        response = client.put(f"/chapters/{locked_id}/draft", json={"body": "x"})

        assert response.status_code == 409
