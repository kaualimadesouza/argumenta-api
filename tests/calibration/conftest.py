import pytest


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Overrides the root autouse fixture: calibration touches no table, and
    depending on it would make the whole suite need Postgres. The nightly job
    runs without a database, and the pure tests here run anywhere."""
    return None
