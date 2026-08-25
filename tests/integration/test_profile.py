"""PATCH /me: the nickname the student can actually fix."""

from fastapi.testclient import TestClient
from tests.integration.conftest import REGISTER


def _register(client: TestClient) -> None:
    assert client.post("/auth/register", json=REGISTER).status_code == 201


def test_the_student_renames_themselves(client: TestClient) -> None:
    _register(client)

    response = client.patch("/me", json={"nickname": "Kauã"})

    assert response.status_code == 200
    assert response.json()["nickname"] == "Kauã"
    assert client.get("/me").json()["user"]["nickname"] == "Kauã"


def test_a_blank_nickname_is_refused(client: TestClient) -> None:
    _register(client)

    assert client.patch("/me", json={"nickname": "   "}).status_code == 422
    assert client.get("/me").json()["user"]["nickname"] == "Aluno"


def test_a_nickname_longer_than_the_column_is_refused(client: TestClient) -> None:
    _register(client)

    assert client.patch("/me", json={"nickname": "a" * 41}).status_code == 422


def test_surrounding_whitespace_is_trimmed(client: TestClient) -> None:
    _register(client)

    assert client.patch("/me", json={"nickname": "  Bete  "}).json()["nickname"] == "Bete"


def test_renaming_requires_a_session(client: TestClient) -> None:
    assert client.patch("/me", json={"nickname": "Bete"}).status_code == 401


def test_registering_with_a_blank_nickname_is_refused(client: TestClient) -> None:
    payload = REGISTER | {"nickname": "  "}

    assert client.post("/auth/register", json=payload).status_code == 422
