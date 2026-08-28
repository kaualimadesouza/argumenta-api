"""The domain-error to HTTP-status map is maintained by hand and the handler falls
back to 400, so drift in either direction is silent. These two tests close it."""

from argumenta.domain import errors
from argumenta.entrypoints.rest_application import ERROR_STATUS


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
