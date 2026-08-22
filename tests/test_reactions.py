"""Issue #10: AI character reaction to the student's text, tests first (TDD)."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import CharacterReaction
from argumenta.application.reactions.ports import ReactionRequest, ReactionText
from argumenta.domain.enums import ReactionBeat, Verdict
from argumenta.domain.errors import EvaluationFailedError, LlmBudgetExceededError
from argumenta.domain.reactions import reaction_beat_for
from argumenta.presentation.fastapi.dependencies import (
    get_llm_budget,
    get_reaction_engine,
)
from tests.conftest import ScriptedEngine, submit_text


class TestReactionBeatRule:
    def test_approved_convinces_the_character(self) -> None:
        assert reaction_beat_for(Verdict.APPROVED) == ReactionBeat.CONVINCED

    def test_persuasion_failure_gets_a_rebuttal(self) -> None:
        assert reaction_beat_for(Verdict.FAILED_PERSUASION) == ReactionBeat.REBUTTAL

    def test_technical_failure_has_no_reaction(self) -> None:
        assert reaction_beat_for(Verdict.FAILED_TECHNICAL) is None


class FakeReactionEngine:
    def __init__(self) -> None:
        self.calls: list[ReactionRequest] = []
        self.fail_with: Exception | None = None

    def generate(self, request: ReactionRequest) -> ReactionText:
        self.calls.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        return ReactionText(
            body=f'{request.character_name} responde citando "palavra".',
            model="claude-sonnet-5",
            prompt_version="react-v1.0",
            output_tokens=42,
        )


@pytest.fixture
def reaction_engine(app: FastAPI) -> FakeReactionEngine:
    fake = FakeReactionEngine()
    app.dependency_overrides[get_reaction_engine] = lambda: fake
    return fake


def _submission_id(
    client: TestClient, chapter_id: uuid.UUID, engine: ScriptedEngine, profile: str
) -> str:
    engine.scripted = profile
    response = submit_text(client, chapter_id)
    assert response.status_code == 201
    return str(response.json()["submission_id"])


class TestReactionEndpoint:
    def test_approved_reaction_is_convinced_and_persisted_with_tokens(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")

        response = client.post(f"/submissions/{submission_id}/reaction")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["beat"] == "convinced"
        assert body["character_name"] == "Dona Marta"
        assert "palavra" in body["body"]
        with Session(db_engine) as session:
            stored = session.scalars(select(CharacterReaction)).one()
        assert stored.beat == ReactionBeat.CONVINCED
        assert stored.output_tokens == 42
        assert stored.model == "claude-sonnet-5"
        assert stored.prompt_version == "react-v1.0"

    def test_persuasion_failure_gets_a_rebuttal_reaction(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "failed_persuasion")

        body = client.post(f"/submissions/{submission_id}/reaction").json()

        assert body["beat"] == "rebuttal"
        request = reaction_engine.calls[0]
        assert request.verdict == Verdict.FAILED_PERSUASION
        assert "palavra" in request.student_text

    def test_technical_failure_has_no_reaction_content(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "failed_technical")

        response = client.post(f"/submissions/{submission_id}/reaction")

        assert response.status_code == 204
        assert reaction_engine.calls == []

    def test_reaction_is_generated_once_and_reused(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")

        first = client.post(f"/submissions/{submission_id}/reaction").json()
        second = client.post(f"/submissions/{submission_id}/reaction").json()

        assert first["body"] == second["body"]
        assert len(reaction_engine.calls) == 1

    def test_engine_failure_falls_back_to_the_scripted_beat(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        reaction_engine.fail_with = EvaluationFailedError("api down")
        submission_id = _submission_id(client, chapter_id, engine_double, "failed_persuasion")

        response = client.post(f"/submissions/{submission_id}/reaction")

        assert response.status_code == 200
        body = response.json()
        # first dialogue beat of the consequence branch of chapter 1
        assert body["body"].startswith("Bonito, mas e o mesmo discurso")
        with Session(db_engine) as session:
            stored = session.scalars(select(CharacterReaction)).one()
        assert stored.model == "fallback"

    def test_exhausted_budget_also_falls_back(
        self,
        app: FastAPI,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
    ) -> None:
        client, chapter_id = game

        submission_id = _submission_id(client, chapter_id, engine_double, "failed_persuasion")

        class ExhaustedBudget:
            def ensure_within_budget(self) -> None:
                raise LlmBudgetExceededError

        app.dependency_overrides[get_llm_budget] = lambda: ExhaustedBudget()

        response = client.post(f"/submissions/{submission_id}/reaction")

        assert response.status_code == 200
        assert reaction_engine.calls == []
        assert response.json()["body"].startswith("Bonito, mas e o mesmo discurso")

    def test_someone_elses_submission_is_not_found(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")
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

        assert client.post(f"/submissions/{submission_id}/reaction").status_code == 404
