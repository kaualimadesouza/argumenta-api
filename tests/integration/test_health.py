from fastapi.testclient import TestClient

from argumenta import __version__
from argumenta.entrypoints.rest_application import create_app


def test_health_returns_status_and_version() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
