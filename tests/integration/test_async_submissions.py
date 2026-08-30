"""Integration tests of the async submission contract (issue #68): POST answers
202 with a pending submission, the worker evaluates out of band, and
GET /submissions/{id} serves the polling until the verdict lands."""

import uuid
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session
from tests.integration.conftest import REGISTER, ScriptedEngine, submit_text

from argumenta.adapters.db.models import ChapterProgress, DailyActivity, Evaluation, Submission
from argumenta.adapters.db.repositories.accounts import SqlAlchemyExamTargetRepository
from argumenta.adapters.db.repositories.gameplay import (
    SqlAlchemyDailyActivityWriter,
    SqlAlchemyDraftRepository,
    SqlAlchemyEvaluationContextRepository,
    SqlAlchemyProgressWriter,
    SqlAlchemySubmissionRepository,
)
from argumenta.adapters.db.repositories.llm_budget import SqlLlmBudget
from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.application.evaluation.ports import EngineRequest, EngineResult
from argumenta.application.evaluation.use_cases import EvaluateArgumentUseCase
from argumenta.application.gameplay.use_cases import (
    EvaluateSubmissionUseCase,
    RecordEvaluationFailureUseCase,
)
from argumenta.domain.enums import ChapterStatus, SubmissionStatus
from argumenta.domain.errors import EvaluationFailedError
from argumenta.presentation.fastapi.dependencies import get_evaluation_dispatcher


class RecordingDispatcher:
    """Dispatcher double: the hand-off is recorded, never executed, so tests can
    observe the pending state and run the worker explicitly."""

    def __init__(self) -> None:
        self.dispatched: list[uuid.UUID] = []

    def dispatch(self, submission_id: uuid.UUID) -> None:
        self.dispatched.append(submission_id)


class ExplodingEngine:
    def evaluate(self, request: EngineRequest) -> EngineResult:
        raise EvaluationFailedError("engine down")


@pytest.fixture
def dispatcher_double() -> RecordingDispatcher:
    return RecordingDispatcher()


@pytest.fixture
def pending_game(
    app: FastAPI,
    game: tuple[TestClient, uuid.UUID],
    dispatcher_double: RecordingDispatcher,
) -> tuple[TestClient, uuid.UUID]:
    app.dependency_overrides[get_evaluation_dispatcher] = lambda: dispatcher_double
    return game


def run_worker(
    db_engine: Engine, engine: ScriptedEngine | ExplodingEngine, submission_id: uuid.UUID
) -> None:
    """Runs the evaluation exactly as the worker entrypoint wires it, with the
    scripted engine in place of the real LLM."""
    with Session(db_engine) as session:
        use_case = EvaluateSubmissionUseCase(
            contexts=SqlAlchemyEvaluationContextRepository(session),
            submissions=SqlAlchemySubmissionRepository(session),
            progress=SqlAlchemyProgressWriter(session),
            activity=SqlAlchemyDailyActivityWriter(session),
            drafts=SqlAlchemyDraftRepository(session),
            evaluate=EvaluateArgumentUseCase(
                engine,
                SpyllsSpellChecker(),
                SqlLlmBudget(session, monthly_token_budget=0, alert_ratio=0.8),
            ),
            exams=SqlAlchemyExamTargetRepository(session),
        )
        use_case.execute(submission_id)
        session.commit()


def record_failure(db_engine: Engine, submission_id: uuid.UUID) -> None:
    with Session(db_engine) as session:
        RecordEvaluationFailureUseCase(
            submissions=SqlAlchemySubmissionRepository(session),
            activity=SqlAlchemyDailyActivityWriter(session),
        ).execute(submission_id)
        session.commit()


class TestAcceptedSubmission:
    def test_post_answers_202_and_hands_off_to_the_dispatcher(
        self,
        pending_game: tuple[TestClient, uuid.UUID],
        dispatcher_double: RecordingDispatcher,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = pending_game

        response = submit_text(client, chapter_id)

        assert response.status_code == 202, response.text
        body = response.json()
        assert body["status"] == "evaluating"
        assert body["attempt_number"] == 1
        assert dispatcher_double.dispatched == [uuid.UUID(body["submission_id"])]
        with Session(db_engine) as session:
            row = session.scalars(select(Submission)).one()
            assert row.status == SubmissionStatus.EVALUATING
            assert session.scalars(select(Evaluation)).all() == []
            progress = session.scalars(
                select(ChapterProgress).where(ChapterProgress.chapter_id == chapter_id)
            ).one()
            assert progress.attempts == 0

    def test_get_serves_evaluating_before_the_verdict(
        self, pending_game: tuple[TestClient, uuid.UUID]
    ) -> None:
        client, chapter_id = pending_game
        submission_id = submit_text(client, chapter_id).json()["submission_id"]

        body = client.get(f"/submissions/{submission_id}").json()

        assert body["submission_id"] == submission_id
        assert body["chapter_id"] == str(chapter_id)
        assert body["status"] == "evaluating"
        assert body["result"] is None


class TestWorker:
    def test_worker_stores_the_verdict_and_get_serves_it(
        self,
        pending_game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = pending_game
        submission_id = submit_text(client, chapter_id).json()["submission_id"]

        run_worker(db_engine, engine_double, uuid.UUID(submission_id))

        body = client.get(f"/submissions/{submission_id}").json()
        assert body["status"] == "evaluated"
        result = body["result"]
        assert result["verdict"] == "approved"
        assert result["chapter_status"] == "passed"
        assert result["average_score"] == 80
        assert result["floor_value"] == 40
        assert result["min_average"] == 50
        assert {s["dimension"] for s in result["scores"]} == {
            "norma_culta",
            "coesao",
            "coerencia",
            "repertorio",
            "persuasao",
        }
        assert result["annotations"] == []
        assert result["para_passar"] == []
        assert result["lens"]["criteria"]
        with Session(db_engine) as session:
            progress = session.scalars(
                select(ChapterProgress).where(ChapterProgress.chapter_id == chapter_id)
            ).one()
            assert progress.status == ChapterStatus.PASSED
            assert str(progress.passing_submission_id) == submission_id
            assert progress.attempts == 1
            assert session.scalars(select(DailyActivity)).one().approved_count == 1

    def test_worker_redelivery_is_idempotent(
        self,
        pending_game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = pending_game
        submission_id = uuid.UUID(submit_text(client, chapter_id).json()["submission_id"])

        run_worker(db_engine, engine_double, submission_id)
        run_worker(db_engine, engine_double, submission_id)

        with Session(db_engine) as session:
            assert len(session.scalars(select(Evaluation)).all()) == 1
            progress = session.scalars(
                select(ChapterProgress).where(ChapterProgress.chapter_id == chapter_id)
            ).one()
            assert progress.attempts == 1

    def test_a_late_verdict_never_regresses_a_passed_chapter(
        self,
        pending_game: tuple[TestClient, uuid.UUID],
        engine_double: ScriptedEngine,
        db_engine: Engine,
    ) -> None:
        client, chapter_id = pending_game
        first = uuid.UUID(submit_text(client, chapter_id).json()["submission_id"])
        second = uuid.UUID(submit_text(client, chapter_id).json()["submission_id"])

        run_worker(db_engine, engine_double, first)
        engine_double.scripted = "failed_technical"
        run_worker(db_engine, engine_double, second)

        body = client.get(f"/submissions/{second}").json()
        assert body["status"] == "evaluated"
        assert body["result"]["verdict"] == "failed_technical"
        assert body["result"]["chapter_status"] == "passed"
        with Session(db_engine) as session:
            progress = session.scalars(
                select(ChapterProgress).where(ChapterProgress.chapter_id == chapter_id)
            ).one()
            assert progress.status == ChapterStatus.PASSED
            assert progress.passing_submission_id == first


class TestRecoverableFailure:
    def test_failure_is_recoverable_and_refunds_the_daily_tick(
        self,
        pending_game: tuple[TestClient, uuid.UUID],
        db_engine: Engine,
    ) -> None:
        client, chapter_id = pending_game
        submission_id = uuid.UUID(submit_text(client, chapter_id).json()["submission_id"])

        with pytest.raises(EvaluationFailedError):
            run_worker(db_engine, ExplodingEngine(), submission_id)
        record_failure(db_engine, submission_id)

        body = client.get(f"/submissions/{submission_id}").json()
        assert body["status"] == "failed"
        assert body["result"] is None
        with Session(db_engine) as session:
            assert session.scalars(select(DailyActivity)).one().submissions_count == 0
        retry = submit_text(client, chapter_id)
        assert retry.status_code == 202
        assert retry.json()["attempt_number"] == 2

    def test_a_submission_stuck_in_evaluating_reports_failed(
        self,
        pending_game: tuple[TestClient, uuid.UUID],
        db_engine: Engine,
    ) -> None:
        client, chapter_id = pending_game
        submission_id = uuid.UUID(submit_text(client, chapter_id).json()["submission_id"])
        with Session(db_engine) as session:
            session.execute(
                update(Submission)
                .where(Submission.id == submission_id)
                .values(created_at=Submission.created_at - timedelta(minutes=5))
            )
            session.commit()

        body = client.get(f"/submissions/{submission_id}").json()

        assert body["status"] == "failed"
        assert body["result"] is None


class TestOwnership:
    def test_get_is_scoped_to_the_owner(
        self,
        app: FastAPI,
        pending_game: tuple[TestClient, uuid.UUID],
    ) -> None:
        client, chapter_id = pending_game
        submission_id = submit_text(client, chapter_id).json()["submission_id"]

        with TestClient(app) as intruder:
            other = dict(REGISTER, email="outra@example.com", nickname="Outra")
            assert intruder.post("/auth/register", json=other).status_code == 201
            assert intruder.get(f"/submissions/{submission_id}").status_code == 404

    def test_unknown_submission_is_404(self, game: tuple[TestClient, uuid.UUID]) -> None:
        client, _ = game
        assert client.get(f"/submissions/{uuid.uuid4()}").status_code == 404


class TestInlineDispatch:
    def test_the_default_local_dispatcher_evaluates_in_the_same_request(
        self, game: tuple[TestClient, uuid.UUID]
    ) -> None:
        """Local dev has no queue: POST still answers 202, but the first GET
        already finds the verdict."""
        client, chapter_id = game

        response = submit_text(client, chapter_id)

        assert response.status_code == 202, response.text
        submission_id = response.json()["submission_id"]
        body = client.get(f"/submissions/{submission_id}").json()
        assert body["status"] == "evaluated"
        assert body["result"]["verdict"] == "approved"
