from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from argumenta.adapters.db.base import Base
from argumenta.adapters.db.session import get_engine
from argumenta.adapters.security.rate_limiter import SlidingWindowRateLimiter
from argumenta.domain.accounts import GoogleIdentity
from argumenta.domain.errors import GoogleSignInFailedError
from argumenta.entrypoints.rest_application import create_app
from argumenta.presentation.fastapi.dependencies import (
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
