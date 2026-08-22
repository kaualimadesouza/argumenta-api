"""Issue #10: AI character reaction to the student's text, tests first (TDD).

Issue #33 adds the race, the authored fallback rule and the repository
get-or-create, which the first round left to the database alone.
"""

import uuid
from collections.abc import Callable

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
from argumenta.adapters.db.repositories.reactions import SqlAlchemyReactionRepository
from argumenta.application.reactions.ports import ReactionRequest, ReactionText
from argumenta.domain.enums import BeatType, ReactionBeat, Verdict
from argumenta.domain.errors import EvaluationFailedError, LlmBudgetExceededError
from argumenta.domain.reactions import (
    CONVINCED_FALLBACK,
    REBUTTAL_FALLBACK,
    needs_authored_line,
    reaction_beat_for,
    scripted_reaction,
)
from argumenta.domain.track import BeatContent
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


class TestScriptedReactionRule:
    """The line the character plays when the AI cannot speak for them."""

    @staticmethod
    def _beat(beat_type: BeatType, body: str) -> BeatContent:
        return BeatContent(
            beat_type=beat_type,
            body=body,
            character_name="Dona Marta",
            character_portrait=None,
            illustration_asset=None,
        )

    def test_a_convinced_beat_has_no_authored_equivalent(self) -> None:
        authored = [self._beat(BeatType.DIALOGUE, "fala escrita a mao")]

        assert scripted_reaction(ReactionBeat.CONVINCED, authored) == CONVINCED_FALLBACK

    def test_a_rebuttal_plays_the_first_authored_dialogue(self) -> None:
        authored = [
            self._beat(BeatType.NARRATION, "a diretora fecha a pasta"),
            self._beat(BeatType.DIALOGUE, "primeira fala"),
            self._beat(BeatType.DIALOGUE, "segunda fala"),
        ]

        assert scripted_reaction(ReactionBeat.REBUTTAL, authored) == "primeira fala"

    def test_a_rebuttal_without_authored_dialogue_still_answers(self) -> None:
        authored = [self._beat(BeatType.NARRATION, "so narracao aqui")]

        assert scripted_reaction(ReactionBeat.REBUTTAL, authored) == REBUTTAL_FALLBACK

    def test_only_a_rebuttal_needs_the_authored_scene(self) -> None:
        """Which is why the use case does not pay for that query otherwise."""
        assert needs_authored_line(ReactionBeat.REBUTTAL) is True
        assert needs_authored_line(ReactionBeat.CONVINCED) is False


class FakeReactionEngine:
    def __init__(self) -> None:
        self.calls: list[ReactionRequest] = []
        self.fail_with: Exception | None = None
        self.before_return: Callable[[], None] | None = None
        """Runs while the call is in flight: how a test plays the other side
        of a race without threads."""

    def generate(self, request: ReactionRequest) -> ReactionText:
        self.calls.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if self.before_return is not None:
            self.before_return()
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
        assert body["provisional"] is False, "a real reaction is not a placeholder"
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
        assert body["provisional"] is True, (
            "the client has to be able to tell a scripted line from a real one"
        )
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
        assert response.json()["provisional"] is True
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


class TestReactionRace:
    """Two POSTs for the same beat at the same time: the partial unique decides
    which line is stored, and both clients have to read that one."""

    def test_the_loser_of_the_race_reads_the_line_that_was_stored(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")
        reaction_engine.before_return = lambda: _store_competing_reaction(
            db_engine, uuid.UUID(submission_id), "fala do vencedor"
        )

        body = client.post(f"/submissions/{submission_id}/reaction").json()

        assert body["body"] == "fala do vencedor", (
            "returning its own unpersisted text would show the student a line "
            "that a refresh then rewrites"
        )
        with Session(db_engine) as session:
            stored = session.scalars(select(CharacterReaction)).one()
        assert stored.body == "fala do vencedor"


class TestReactionRepository:
    def test_store_or_get_keeps_the_first_line_and_returns_it(
        self,
        game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        reaction_engine: FakeReactionEngine,
        db_engine: Engine,
    ) -> None:
        """The ON CONFLICT branch, which no test reached before: a wrong
        index_where would raise 42P10 here and only in a real race."""
        client, chapter_id = game
        submission_id = _submission_id(client, chapter_id, engine_double, "approved")
        assert client.post(f"/submissions/{submission_id}/reaction").status_code == 200

        with Session(db_engine) as session:
            stored = session.scalars(select(CharacterReaction)).one()
            first_body = stored.body
            body = SqlAlchemyReactionRepository(session).store_or_get(
                stored.submission_id,
                stored.character_id,
                stored.beat,
                ReactionText(
                    body="segunda fala do mesmo beat",
                    model="claude-sonnet-5",
                    prompt_version="react-v1.0",
                    input_tokens=1,
                    output_tokens=1,
                ),
            )
            session.commit()

        assert body == first_body
        with Session(db_engine) as session:
            rows = session.scalars(select(CharacterReaction)).all()
        assert [row.body for row in rows] == [first_body]


def _store_competing_reaction(db_engine: Engine, submission_id: uuid.UUID, body: str) -> None:
    with Session(db_engine) as session:
        character_id = session.scalar(select(Character.id).where(Character.name == "Dona Marta"))
        session.add(
            CharacterReaction(
                submission_id=submission_id,
                character_id=character_id,
                beat=ReactionBeat.CONVINCED,
                body=body,
                model="claude-sonnet-5",
                prompt_version="react-v1.0",
                input_tokens=900,
                output_tokens=42,
            )
        )
        session.commit()
