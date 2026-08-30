"""GET /progress: the aggregate behind the Progresso screen (mockup 07)."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session
from tests.integration.conftest import REGISTER, ScriptedEngine, submit_text

from argumenta.adapters.db.seed.tutorial import seed_tutorial

BOSS_TEXT = " ".join(["palavra"] * 300)


@pytest.fixture
def student(client: TestClient, db_engine: Engine) -> TestClient:
    """Registered, tutorial seeded, nothing played yet."""
    with Session(db_engine) as session:
        seed_tutorial(session)
        session.commit()
    assert client.post("/auth/register", json=REGISTER).status_code == 201
    return client


def _practice_on(db_engine: Engine, days: list[date]) -> None:
    with Session(db_engine) as session:
        user_id = session.scalar(text("SELECT id FROM users LIMIT 1"))
        for day in days:
            session.execute(
                text(
                    "INSERT INTO daily_activity (user_id, activity_date, submissions_count) "
                    "VALUES (:user_id, :day, 1) ON CONFLICT DO NOTHING"
                ),
                {"user_id": user_id, "day": day},
            )
        session.commit()


def _age_submissions(db_engine: Engine, days: int) -> None:
    with Session(db_engine) as session:
        session.execute(
            text("UPDATE submissions SET created_at = created_at - make_interval(days => :days)"),
            {"days": days},
        )
        session.commit()


class TestEmptyProgress:
    def test_a_student_who_never_wrote_sees_zeros_and_the_five_dimensions(
        self, student: TestClient
    ) -> None:
        body = student.get("/progress").json()

        assert body["streak_days"] == 0
        assert body["longest_streak_days"] == 0
        assert body["stories_completed"] == 0
        assert body["stories_total"] == 1
        assert [d["dimension"] for d in body["dimensions"]] == [
            "norma_culta",
            "coesao",
            "coerencia",
            "repertorio",
            "persuasao",
        ]
        assert all(d["points"] == [] for d in body["dimensions"])
        assert all(m["done"] is False for m in body["milestones"])

    def test_progress_requires_a_session(self, client: TestClient) -> None:
        assert client.get("/progress").status_code == 401


class TestSeries:
    def test_an_evaluated_submission_becomes_one_point_per_dimension(
        self, game: tuple[TestClient, uuid.UUID]
    ) -> None:
        client, chapter_id = game
        assert submit_text(client, chapter_id).status_code == 202

        body = client.get("/progress").json()

        series = {d["dimension"]: d["points"] for d in body["dimensions"]}
        assert len(series["norma_culta"]) == 1
        assert series["norma_culta"][0]["score"] == 80
        assert body["streak_days"] == 1
        assert body["longest_streak_days"] == 1

    def test_samples_older_than_the_window_are_left_out(
        self, game: tuple[TestClient, uuid.UUID], db_engine: Engine
    ) -> None:
        client, chapter_id = game
        assert submit_text(client, chapter_id).status_code == 202
        _age_submissions(db_engine, days=40)

        body = client.get("/progress").json()

        assert all(d["points"] == [] for d in body["dimensions"])

    def test_the_proposal_dimension_only_shows_up_once_it_was_graded(
        self, boss_game: tuple[TestClient, uuid.UUID]
    ) -> None:
        client, boss_chapter_id = boss_game
        before = client.get("/progress").json()
        assert submit_text(client, boss_chapter_id, body=BOSS_TEXT).status_code == 202

        after = client.get("/progress").json()

        assert "proposta_intervencao" not in [d["dimension"] for d in before["dimensions"]]
        assert "proposta_intervencao" in [d["dimension"] for d in after["dimensions"]]


class TestStreak:
    def test_the_record_survives_a_streak_the_student_broke(
        self, student: TestClient, db_engine: Engine
    ) -> None:
        today = date.today()
        _practice_on(db_engine, [today - timedelta(days=n) for n in (10, 11, 12, 13)])

        body = student.get("/progress").json()

        assert body["streak_days"] == 0
        assert body["longest_streak_days"] == 4

    def test_a_week_without_missing_is_a_milestone(
        self, student: TestClient, db_engine: Engine
    ) -> None:
        today = date.today()
        _practice_on(db_engine, [today - timedelta(days=n) for n in range(7)])

        body = student.get("/progress").json()

        done = {m["code"] for m in body["milestones"] if m["done"]}
        assert "week_without_missing" in done


class TestMilestones:
    def test_finishing_the_tutorial_marks_the_story_and_the_boss(
        self, boss_game: tuple[TestClient, uuid.UUID], engine_double: ScriptedEngine
    ) -> None:
        client, boss_chapter_id = boss_game
        engine_double.scripted = "approved"
        assert submit_text(client, boss_chapter_id, body=BOSS_TEXT).status_code == 202

        body = client.get("/progress").json()

        done = {m["code"] for m in body["milestones"] if m["done"]}
        assert "tutorial_completed" in done
        assert "first_boss_essay" in done
        assert body["stories_completed"] == 1


class TestLens:
    def test_enem_labels_the_dimensions_with_its_competences(self, student: TestClient) -> None:
        student.post("/me/targets", json={"exam": "enem", "year": 2027})

        body = student.get("/progress").json()

        codes = {d["dimension"]: d["criterion_code"] for d in body["dimensions"]}
        assert body["exam"] == "enem"
        assert codes["norma_culta"] == "C1"
        assert codes["persuasao"] == "ARG"

    def test_fuvest_labels_the_same_dimensions_with_its_axes(self, student: TestClient) -> None:
        student.post("/me/targets", json={"exam": "fuvest", "year": 2027})

        body = student.get("/progress").json()

        codes = {d["dimension"]: d["criterion_code"] for d in body["dimensions"]}
        assert body["exam"] == "fuvest"
        assert codes["norma_culta"] == "E3"
        assert codes["coesao"] == "E2"
        assert codes["coerencia"] == "E2"
