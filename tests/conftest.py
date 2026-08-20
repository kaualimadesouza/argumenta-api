import uuid
from collections.abc import Iterator
from typing import ClassVar

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from argumenta.adapters.db.base import Base
from argumenta.adapters.db.models import Chapter
from argumenta.adapters.db.seed.tutorial import seed_tutorial
from argumenta.adapters.db.session import get_engine
from argumenta.adapters.security.rate_limiter import SlidingWindowRateLimiter
from argumenta.application.evaluation.ports import EngineRequest, EngineResult
from argumenta.domain.accounts import GoogleIdentity
from argumenta.domain.enums import Dimension
from argumenta.domain.errors import GoogleSignInFailedError
from argumenta.domain.evaluation import DimensionScore
from argumenta.entrypoints.rest_application import create_app
from argumenta.presentation.fastapi.dependencies import (
    get_evaluation_engine,
    get_google_gateway,
    get_rate_limiter,
)


class FakeGoogleGateway:
    """Test double for the Google code exchange; tests set `identity`."""

    def __init__(self) -> None:
        self.identity: GoogleIdentity | None = None

    def exchange_code(self, code: str, redirect_uri: str) -> GoogleIdentity:
        if self.identity is None:
            raise GoogleSignInFailedError("no identity configured in the fake")
        return self.identity


@pytest.fixture(scope="session")
def db_engine() -> Engine:
    command.upgrade(Config("alembic.ini"), "head")
    return get_engine()


@pytest.fixture(autouse=True)
def clean_database(db_engine: Engine) -> Iterator[None]:
    yield
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with db_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def google_gateway() -> FakeGoogleGateway:
    return FakeGoogleGateway()


@pytest.fixture
def rate_limiter() -> SlidingWindowRateLimiter:
    return SlidingWindowRateLimiter(max_attempts=5, window_seconds=300)


@pytest.fixture
def app(
    db_engine: Engine,
    google_gateway: FakeGoogleGateway,
    rate_limiter: SlidingWindowRateLimiter,
) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_google_gateway] = lambda: google_gateway
    application.dependency_overrides[get_rate_limiter] = lambda: rate_limiter
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


REGISTER = {
    "email": "aluno@example.com",
    "nickname": "Aluno",
    "password": "correct-horse-9",  # pragma: allowlist secret
    "accepted_terms": True,
}

TEXT_130_WORDS = " ".join(["palavra"] * 130)


class ScriptedEngine:
    """Engine double: yields scores per profile; set `scripted` before submitting."""

    PROFILES: ClassVar[dict[str, dict[Dimension, int]]] = {
        "approved": {},
        "failed_technical": {Dimension.NORMA_CULTA: 20},
        "failed_persuasion": {Dimension.PERSUASAO: 20},
    }

    def __init__(self) -> None:
        self.scripted = "approved"
        self.calls: list[EngineRequest] = []

    def evaluate(self, request: EngineRequest) -> EngineResult:
        self.calls.append(request)
        overrides = self.PROFILES[self.scripted]
        scores = tuple(
            DimensionScore(dimension=d, score=overrides.get(d, 80), evidence="trecho")
            for d in (
                Dimension.NORMA_CULTA,
                Dimension.COESAO,
                Dimension.COERENCIA,
                Dimension.REPERTORIO,
                Dimension.PERSUASAO,
            )
        )
        return EngineResult(
            scores=scores,
            annotations=(),
            model="claude-sonnet-5",
            prompt_version="eval-v1.0",
            latency_ms=5,
            input_tokens=100,
            output_tokens=50,
        )


@pytest.fixture
def engine_double() -> ScriptedEngine:
    return ScriptedEngine()


@pytest.fixture
def game(
    app: FastAPI,
    client: TestClient,
    db_engine: Engine,
    engine_double: ScriptedEngine,
) -> tuple[TestClient, uuid.UUID]:
    """Seeded tutorial + registered user + first chapter unlocked via /track."""
    app.dependency_overrides[get_evaluation_engine] = lambda: engine_double
    with Session(db_engine) as session:
        seed_tutorial(session)
        session.commit()
    assert client.post("/auth/register", json=REGISTER).status_code == 201
    assert client.get("/track").status_code == 200
    with Session(db_engine) as session:
        chapter_id = session.scalar(select(Chapter.id).where(Chapter.position == 1))
    assert chapter_id is not None
    return client, chapter_id


def submit_text(client: TestClient, chapter_id: uuid.UUID, body: str = TEXT_130_WORDS) -> Response:
    response: Response = client.post(f"/chapters/{chapter_id}/submissions", json={"body": body})
    return response
