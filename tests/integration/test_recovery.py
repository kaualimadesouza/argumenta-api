"""Issue #9: consequence branch and recovery scene, tests written first (TDD).

Reuses the ScriptedEngine double and the seeded-game fixture from
tests/test_submissions.py.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from tests.integration.conftest import ScriptedEngine
from tests.integration.conftest import submit_and_correction as _correction
from tests.integration.conftest import submit_text as _submit

from argumenta.adapters.db.models import Chapter, ChapterProgress, Submission
from argumenta.domain.enums import ChapterStatus, SubmissionContext
from argumenta.domain.errors import ChapterNotWritableError
from argumenta.domain.submission import start_recovery


class TestStartRecoveryRule:
    def test_consequence_moves_to_recovery(self) -> None:
        assert start_recovery(ChapterStatus.IN_CONSEQUENCE) == ChapterStatus.IN_RECOVERY

    def test_already_in_recovery_stays_in_recovery(self) -> None:
        assert start_recovery(ChapterStatus.IN_RECOVERY) == ChapterStatus.IN_RECOVERY

    @pytest.mark.parametrize(
        "status",
        [
            ChapterStatus.LOCKED,
            ChapterStatus.AVAILABLE,
            ChapterStatus.DRAFTING,
            ChapterStatus.PASSED,
        ],
    )
    def test_other_states_cannot_start_recovery(self, status: ChapterStatus) -> None:
        with pytest.raises(ChapterNotWritableError):
            start_recovery(status)


def _fail_persuasion(client: TestClient, chapter_id: uuid.UUID, engine: ScriptedEngine) -> None:
    engine.scripted = "failed_persuasion"
    assert _submit(client, chapter_id).status_code == 202


class TestRecoveryFlow:
    def test_recovery_action_serves_the_recovery_branch(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
    ) -> None:
        client, chapter_id = game
        _fail_persuasion(client, chapter_id, engine_double)

        response = client.post(f"/chapters/{chapter_id}/recovery")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "in_recovery"
        assert body["branch"] == "recovery"
        assert body["beats"], "recovery script must come in the same call"

    def test_recovery_action_is_idempotent(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        _fail_persuasion(client, chapter_id, engine_double)

        first = client.post(f"/chapters/{chapter_id}/recovery")
        second = client.post(f"/chapters/{chapter_id}/recovery")

        assert first.status_code == second.status_code == 200
        assert second.json()["status"] == "in_recovery"
        with Session(db_engine) as session:
            status = session.scalar(
                select(ChapterProgress.status).where(ChapterProgress.chapter_id == chapter_id)
            )
        assert status == ChapterStatus.IN_RECOVERY

    def test_recovery_requires_the_consequence_state(
        self, game: tuple[TestClient, uuid.UUID]
    ) -> None:
        client, chapter_id = game

        response = client.post(f"/chapters/{chapter_id}/recovery")

        assert response.status_code == 409

    def test_recovery_submission_is_recorded_with_recovery_context(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        _fail_persuasion(client, chapter_id, engine_double)
        client.post(f"/chapters/{chapter_id}/recovery")
        engine_double.scripted = "approved"

        assert _submit(client, chapter_id).status_code == 202

        with Session(db_engine) as session:
            contexts = list(
                session.scalars(select(Submission.context).order_by(Submission.attempt_number))
            )
        assert contexts == [SubmissionContext.MAIN, SubmissionContext.RECOVERY]

    def test_full_cycle_fail_consequence_recover_approve_unlocks_next(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game

        _fail_persuasion(client, chapter_id, engine_double)
        assert client.get(f"/chapters/{chapter_id}").json()["branch"] == "consequence"

        assert client.post(f"/chapters/{chapter_id}/recovery").status_code == 200

        engine_double.scripted = "approved"
        body = _correction(client, chapter_id)
        assert body["result"]["verdict"] == "approved"
        assert body["result"]["chapter_status"] == "passed"

        # reading the track materializes the next chapter of the story
        assert client.get("/track").status_code == 200
        with Session(db_engine) as session:
            next_chapter = session.scalar(select(Chapter.id).where(Chapter.position == 2))
            status = session.scalar(
                select(ChapterProgress.status).where(ChapterProgress.chapter_id == next_chapter)
            )
        assert status == ChapterStatus.AVAILABLE
