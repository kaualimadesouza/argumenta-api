import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from argumenta.adapters.db.models import (
    Chapter,
    ChapterBeat,
    ChapterProgress,
    Character,
    DailyActivity,
    Story,
)
from argumenta.adapters.db.seed.tutorial import seed_tutorial
from argumenta.domain.enums import ChapterStatus, ContentStatus

REGISTER = {
    "email": "aluno@example.com",
    "nickname": "Aluno",
    "password": "correct-horse-9",  # pragma: allowlist secret
    "accepted_terms": True,
}


@pytest.fixture
def seeded(db_engine: Engine) -> Iterator[None]:
    with Session(db_engine) as session:
        seed_tutorial(session)
        session.commit()
    yield


@pytest.fixture
def second_story(db_engine: Engine) -> uuid.UUID:
    """A minimal published story after the tutorial, to exercise locking."""
    with Session(db_engine) as session:
        story = Story(
            slug="segunda-historia",
            title="Segunda Historia",
            synopsis="A proxima da trilha.",
            position=2,
            dimension_floor=50,
            min_average=60,
            status=ContentStatus.PUBLISHED,
        )
        session.add(story)
        session.flush()
        villain = Character(story_id=story.id, name="Vilao", persona_brief="Duvida de tudo.")
        session.add(villain)
        session.flush()
        session.add(
            Chapter(
                story_id=story.id,
                position=1,
                kind="confronto",
                title="Primeiro embate",
                objective="Convencer o vilao.",
                antagonist_id=villain.id,
                min_words=120,
                max_words=250,
                evaluator_brief="Argumento com evidencia.",
            )
        )
        session.commit()
        return story.id


def _register(client: TestClient) -> uuid.UUID:
    response = client.post("/auth/register", json=REGISTER)
    assert response.status_code == 201
    return uuid.UUID(response.json()["id"])


def test_seed_is_idempotent(db_engine: Engine, seeded: None) -> None:
    with Session(db_engine) as session:
        assert seed_tutorial(session) is False
        session.commit()
        stories = session.scalar(select(func.count()).select_from(Story))
        chapters = session.scalar(select(func.count()).select_from(Chapter))
        beats = session.scalar(select(func.count()).select_from(ChapterBeat))
    assert stories == 1
    assert chapters == 3
    assert beats == 33


def test_new_user_sees_tutorial_available_and_rest_locked(
    client: TestClient, seeded: None, second_story: uuid.UUID
) -> None:
    _register(client)

    response = client.get("/track")
    assert response.status_code == 200
    body = response.json()
    states = {story["slug"]: story["state"] for story in body["stories"]}
    assert states == {"o-gremio": "available", "segunda-historia": "locked"}
    assert body["streak_days"] == 0
    assert body["submissions_today"] == 0
    assert body["daily_limit"] == 3


def test_track_materializes_first_chapter_progress(
    client: TestClient, seeded: None, db_engine: Engine
) -> None:
    user_id = _register(client)
    client.get("/track")

    with Session(db_engine) as session:
        rows = session.execute(
            select(ChapterProgress.status, Chapter.position)
            .join(Chapter, ChapterProgress.chapter_id == Chapter.id)
            .where(ChapterProgress.user_id == user_id)
        ).all()
    assert [(status, pos) for status, pos in rows] == [(ChapterStatus.AVAILABLE, 1)]


def test_chapter_returns_ordered_main_beats_with_characters(
    client: TestClient, seeded: None, db_engine: Engine
) -> None:
    _register(client)
    client.get("/track")
    with Session(db_engine) as session:
        chapter_id = session.scalar(select(Chapter.id).where(Chapter.position == 1))

    response = client.get(f"/chapters/{chapter_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["branch"] == "main"
    assert body["antagonist_name"] == "Dona Marta"
    assert body["min_words"] == 120
    assert body["max_words"] == 250
    assert [beat["beat_type"] for beat in body["beats"]] == [
        "narration",
        "dialogue",
        "objective",
        "hint",
    ]
    dialogue = body["beats"][1]
    assert dialogue["character_name"] == "Dona Marta"


def test_locked_chapter_is_forbidden(client: TestClient, seeded: None, db_engine: Engine) -> None:
    _register(client)
    client.get("/track")
    with Session(db_engine) as session:
        chapter_id = session.scalar(select(Chapter.id).where(Chapter.position == 2))

    assert client.get(f"/chapters/{chapter_id}").status_code == 403


def test_unknown_chapter_not_found(client: TestClient, seeded: None) -> None:
    _register(client)

    response = client.get(f"/chapters/{uuid.uuid4()}")
    assert response.status_code == 404


def test_chapter_in_consequence_serves_the_consequence_branch(
    client: TestClient, seeded: None, db_engine: Engine
) -> None:
    user_id = _register(client)
    client.get("/track")
    with Session(db_engine) as session:
        chapter_id = session.scalar(select(Chapter.id).where(Chapter.position == 1))
        session.execute(
            update(ChapterProgress)
            .where(ChapterProgress.user_id == user_id)
            .values(status=ChapterStatus.IN_CONSEQUENCE)
        )
        session.commit()

    body = client.get(f"/chapters/{chapter_id}").json()
    assert body["branch"] == "consequence"
    assert len(body["beats"]) == 3


def test_completing_tutorial_unlocks_next_story(
    client: TestClient, seeded: None, second_story: uuid.UUID, db_engine: Engine
) -> None:
    user_id = _register(client)
    client.get("/track")
    with Session(db_engine) as session:
        tutorial_chapters = session.scalars(
            select(Chapter.id).join(Story, Chapter.story_id == Story.id).where(Story.position == 1)
        ).all()
        for chapter_id in tutorial_chapters:
            session.merge(
                ChapterProgress(user_id=user_id, chapter_id=chapter_id, status=ChapterStatus.PASSED)
            )
        session.commit()

    body = client.get("/track").json()
    states = {story["slug"]: story["state"] for story in body["stories"]}
    assert states["o-gremio"] == "completed"
    assert states["segunda-historia"] == "available"
    with Session(db_engine) as session:
        unlocked = session.scalar(
            select(func.count())
            .select_from(ChapterProgress)
            .join(Chapter, ChapterProgress.chapter_id == Chapter.id)
            .where(
                ChapterProgress.user_id == user_id,
                Chapter.story_id == second_story,
                ChapterProgress.status == ChapterStatus.AVAILABLE,
            )
        )
    assert unlocked == 1


def test_track_reports_streak_and_daily_submissions(
    client: TestClient, seeded: None, db_engine: Engine
) -> None:
    from datetime import UTC, datetime, timedelta

    user_id = _register(client)
    today = datetime.now(tz=UTC).date()
    with Session(db_engine) as session:
        for offset, submissions in ((0, 2), (1, 1), (2, 3)):
            session.add(
                DailyActivity(
                    user_id=user_id,
                    activity_date=today - timedelta(days=offset),
                    submissions_count=submissions,
                    approved_count=0,
                )
            )
        session.commit()

    body = client.get("/track").json()
    assert body["streak_days"] == 3
    assert body["submissions_today"] == 2


def test_track_requires_authentication(client: TestClient, seeded: None) -> None:
    assert client.get("/track").status_code == 401


def test_track_points_at_the_chapter_to_open(
    client: TestClient, seeded: None, second_story: uuid.UUID, db_engine: Engine
) -> None:
    """The client cannot navigate without a chapter id, and the CTA counts the
    chapter's place in the story ("Continuar capitulo 2"), not its row id."""
    _register(client)

    stories = {story["slug"]: story for story in client.get("/track").json()["stories"]}

    cursor = stories["o-gremio"]["current_chapter"]
    with Session(db_engine) as session:
        first = session.scalar(
            select(Chapter.id)
            .join(Story, Chapter.story_id == Story.id)
            .where(Story.position == 1, Chapter.position == 1)
        )
    assert cursor == {"id": str(first), "order": 1, "status": "available"}
    assert stories["segunda-historia"]["current_chapter"] is None


def test_the_cursor_walks_to_the_next_unfinished_chapter(
    client: TestClient, seeded: None, db_engine: Engine
) -> None:
    user_id = _register(client)
    client.get("/track")
    with Session(db_engine) as session:
        first = session.scalar(
            select(Chapter.id)
            .join(Story, Chapter.story_id == Story.id)
            .where(Story.position == 1, Chapter.position == 1)
        )
        session.merge(
            ChapterProgress(user_id=user_id, chapter_id=first, status=ChapterStatus.PASSED)
        )
        session.commit()

    stories = {story["slug"]: story for story in client.get("/track").json()["stories"]}

    assert stories["o-gremio"]["current_chapter"]["order"] == 2


def test_a_finished_story_has_no_chapter_to_open(
    client: TestClient, seeded: None, second_story: uuid.UUID, db_engine: Engine
) -> None:
    user_id = _register(client)
    client.get("/track")
    with Session(db_engine) as session:
        for chapter_id in session.scalars(
            select(Chapter.id).join(Story, Chapter.story_id == Story.id).where(Story.position == 1)
        ).all():
            session.merge(
                ChapterProgress(user_id=user_id, chapter_id=chapter_id, status=ChapterStatus.PASSED)
            )
        session.commit()

    stories = {story["slug"]: story for story in client.get("/track").json()["stories"]}

    assert stories["o-gremio"]["current_chapter"] is None
    assert stories["segunda-historia"]["current_chapter"]["order"] == 1
