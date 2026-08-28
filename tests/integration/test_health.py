from collections.abc import Callable, Iterator
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, PendingRollbackError
from sqlalchemy.orm import Session

from argumenta import __version__
from argumenta.entrypoints.rest_application import create_app
from argumenta.presentation.fastapi.dependencies import get_db


class BrokenSession:
    """A Session whose database stopped answering, faithful on one point that
    matters: committing an aborted transaction raises, as SQLAlchemy does."""

    def __init__(self) -> None:
        self.executed = 0
        self.rolled_back = False
        self._aborted = False

    def execute(self, *args: object, **kwargs: object) -> object:
        self.executed += 1
        self._aborted = True
        raise OperationalError("SELECT 1", None, Exception("connection refused"))

    def commit(self) -> None:
        if self._aborted:
            raise PendingRollbackError("commit on an aborted transaction")

    def rollback(self) -> None:
        self.rolled_back = True
        self._aborted = False

    def close(self) -> None:
        return None


def _broken_db(session: BrokenSession) -> Callable[[], Iterator[Session]]:
    """Mirrors get_db's teardown so a forgotten rollback fails the test."""

    def dependency() -> Iterator[Session]:
        try:
            yield cast(Session, session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return dependency


def test_health_returns_status_and_version() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__


def test_health_answers_with_the_database_down() -> None:
    """Liveness has to answer without dependencies, or a probe cannot tell a dead
    process from a process that is up and unusable."""
    session = BrokenSession()
    app = create_app()
    app.dependency_overrides[get_db] = _broken_db(session)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert session.executed == 0


def test_ready_reports_the_database_up(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


def test_ready_answers_503_when_the_database_is_down() -> None:
    session = BrokenSession()
    app = create_app()
    app.dependency_overrides[get_db] = _broken_db(session)

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "down"


def test_ready_rolls_the_failed_statement_back() -> None:
    """The failed SELECT leaves the transaction aborted: without the rollback the
    request teardown commits, and the honest 503 becomes a 500."""
    session = BrokenSession()
    app = create_app()
    app.dependency_overrides[get_db] = _broken_db(session)

    TestClient(app).get("/health/ready")

    assert session.rolled_back
