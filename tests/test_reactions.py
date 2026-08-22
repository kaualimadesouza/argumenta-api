"""Issue #10: AI character reaction to the student's text, tests first (TDD)."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import (
    Chapter,
    Character,
    CharacterReaction,
    Evaluation,
)
from argumenta.adapters.db.repositories.llm_budget import SqlLlmBudget
from argumenta.application.reactions.ports import ReactionRequest, ReactionText
from argumenta.domain.enums import ReactionBeat, Verdict
from argumenta.domain.errors import EvaluationFailedError, LlmBudgetExceededError
from argumenta.domain.reactions import reaction_beat_for
from argumenta.presentation.fastapi.dependencies import (
    get_llm_budget,
    get_reaction_engine,
)
from tests.conftest import ScriptedEngine, submit_text


class ExhaustedBudget:
    def ensure_within_budget(self) -> None:
        raise LlmBudgetExceededError


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
            input_tokens=900,
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
        # what the engine wrote reaches the client verbatim; that the reaction
        # really quotes the student is pinned by the request assertions below
        name = reaction_engine.calls[0].character_name
        assert body["body"] == f'{name} responde citando "palavra".'
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
            assert session.scalars(select(CharacterReaction)).all() == [], (
                "a scripted fallback costs no tokens and must not freeze the reaction"
            )

    def test_fallback_is_retried_once_the_engine_recovers(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        reaction_engine.fail_with = EvaluationFailedError("api down")
        submission_id = _submission_id(client, chapter_id, engine_double, "failed_persuasion")
        assert client.post(f"/submissions/{submission_id}/reaction").status_code == 200

        reaction_engine.fail_with = None
        body = client.post(f"/submissions/{submission_id}/reaction").json()

        assert "palavra" in body["body"], "the real reaction replaces the scripted one"
        with Session(db_engine) as session:
            assert session.scalars(select(CharacterReaction)).one().model == "claude-sonnet-5"

    def test_exhausted_budget_also_falls_back(
        self,
        app: FastAPI,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game

        submission_id = _submission_id(client, chapter_id, engine_double, "failed_persuasion")
        app.dependency_overrides[get_llm_budget] = lambda: ExhaustedBudget()

        response = client.post(f"/submissions/{submission_id}/reaction")

        assert response.status_code == 200
        assert reaction_engine.calls == []
        assert response.json()["body"].startswith("Bonito, mas e o mesmo discurso")
        with Session(db_engine) as session:
            assert session.scalars(select(CharacterReaction)).all() == []

    def test_technical_failure_persists_nothing(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "failed_technical")

        assert client.post(f"/submissions/{submission_id}/reaction").status_code == 204

        with Session(db_engine) as session:
            assert session.scalars(select(CharacterReaction)).all() == []

    def test_request_carries_the_persona_and_the_scene_objective(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")

        client.post(f"/submissions/{submission_id}/reaction")

        request = reaction_engine.calls[0]
        with Session(db_engine) as session:
            character = session.scalars(
                select(Character).where(Character.name == "Dona Marta")
            ).one()
            objective = session.scalar(select(Chapter.objective).where(Chapter.id == chapter_id))
        assert request.persona_brief == character.persona_brief
        assert request.chapter_objective == objective

    def test_a_reaction_of_another_beat_does_not_break_the_lookup(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        """The DER keeps consequence_intro and recovery_prompt in this same
        table, so the lookup must be per beat, not per submission."""
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "failed_persuasion")
        with Session(db_engine) as session:
            character_id = session.scalar(
                select(Character.id).where(Character.name == "Dona Marta")
            )
            session.add(
                CharacterReaction(
                    submission_id=uuid.UUID(submission_id),
                    character_id=character_id,
                    beat=ReactionBeat.CONSEQUENCE_INTRO,
                    body="A diretoria mantem a decisao.",
                    model="claude-sonnet-5",
                    prompt_version="react-v1.0",
                    input_tokens=10,
                    output_tokens=5,
                )
            )
            session.commit()

        response = client.post(f"/submissions/{submission_id}/reaction")

        assert response.status_code == 200, response.text
        assert response.json()["beat"] == "rebuttal"

    def test_a_second_reaction_for_the_same_beat_is_refused_by_the_database(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")
        assert client.post(f"/submissions/{submission_id}/reaction").status_code == 200

        with Session(db_engine) as session:
            stored = session.scalars(select(CharacterReaction)).one()
            session.add(
                CharacterReaction(
                    submission_id=stored.submission_id,
                    character_id=stored.character_id,
                    beat=stored.beat,
                    body="segunda fala do mesmo beat",
                    model="claude-sonnet-5",
                    prompt_version="react-v1.0",
                    input_tokens=1,
                    output_tokens=1,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()

    def test_reaction_tokens_count_towards_the_monthly_budget(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        """Input tokens dominate a reaction call, so counting only the output
        would let the beta cap leak by roughly an order of magnitude."""
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")
        client.post(f"/submissions/{submission_id}/reaction")

        with Session(db_engine) as session:
            budget = SqlLlmBudget(session, monthly_token_budget=1)
            with pytest.raises(LlmBudgetExceededError):
                budget.ensure_within_budget()
            stored = session.scalars(select(CharacterReaction)).one()
        assert (stored.input_tokens, stored.output_tokens) == (900, 42)

    def test_a_superseded_evaluation_is_ignored(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        """Re-correction is on the roadmap: only the current evaluation decides
        which beat the character plays."""
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")
        with Session(db_engine) as session:
            current = session.scalars(select(Evaluation)).one()
            session.add(
                Evaluation(
                    submission_id=current.submission_id,
                    is_current=False,
                    verdict=Verdict.FAILED_TECHNICAL,
                    average_score=20,
                    floor_value=40,
                    min_average=50,
                    model="claude-sonnet-5",
                    prompt_version="eval-v1.0",
                )
            )
            session.commit()

        body = client.post(f"/submissions/{submission_id}/reaction").json()

        assert body["beat"] == "convinced"

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
