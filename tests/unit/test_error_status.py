"""The domain-error to HTTP-status map is maintained by hand and the handler falls
back to 400, so drift in either direction is silent. These two tests close it."""

import logging

import pytest
from fastapi.testclient import TestClient

from argumenta.domain import errors
from argumenta.entrypoints.rest_application import ERROR_STATUS, create_app


def _concrete_errors() -> set[type[errors.DomainError]]:
    found: set[type[errors.DomainError]] = set()
    pending: list[type[errors.DomainError]] = [errors.DomainError]
    while pending:
        for subclass in pending.pop().__subclasses__():
            found.add(subclass)
            pending.append(subclass)
    return found


def test_every_domain_error_has_an_explicit_status() -> None:
    unmapped = sorted(error.__name__ for error in _concrete_errors() if error not in ERROR_STATUS)

    assert unmapped == []


def test_the_status_map_has_no_entry_for_a_deleted_error() -> None:
    concrete = _concrete_errors()
    stale = sorted(error.__name__ for error in ERROR_STATUS if error not in concrete)

    assert stale == []


def test_a_5xx_domain_error_is_logged_with_its_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Caught live: the engine failed, the student saw 502 and the server kept
    no trace of why. The message stays out of the response on purpose; the log
    is where it must land."""
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise errors.EvaluationFailedError("the vendor said no")

    with caplog.at_level(logging.ERROR):
        response = TestClient(app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 502
    assert response.json() == {"detail": "EvaluationFailedError"}
    assert "the vendor said no" in caplog.text
