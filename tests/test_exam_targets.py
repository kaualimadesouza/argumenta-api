from fastapi.testclient import TestClient

REGISTER = {
    "email": "aluno@example.com",
    "nickname": "Aluno",
    "password": "correct-horse-9",  # pragma: allowlist secret
    "accepted_terms": True,
}


def _register(client: TestClient) -> None:
    assert client.post("/auth/register", json=REGISTER).status_code == 201


def test_first_target_becomes_the_active_lens(client: TestClient) -> None:
    _register(client)

    response = client.post("/me/targets", json={"exam": "enem", "year": 2027})
    assert response.status_code == 201
    assert response.json()["is_active"] is True


def test_second_target_is_not_active(client: TestClient) -> None:
    _register(client)
    client.post("/me/targets", json={"exam": "enem", "year": 2027})

    response = client.post("/me/targets", json={"exam": "fuvest", "year": 2027})
    assert response.status_code == 201
    assert response.json()["is_active"] is False


def test_duplicate_target_conflicts(client: TestClient) -> None:
    _register(client)
    client.post("/me/targets", json={"exam": "enem", "year": 2027})

    response = client.post("/me/targets", json={"exam": "enem", "year": 2027})
    assert response.status_code == 409


def test_activate_switches_the_lens(client: TestClient) -> None:
    _register(client)
    client.post("/me/targets", json={"exam": "enem", "year": 2027})
    fuvest_id = client.post("/me/targets", json={"exam": "fuvest", "year": 2027}).json()["id"]

    assert client.put(f"/me/targets/{fuvest_id}/activate").status_code == 204

    targets = {t["exam"]: t["is_active"] for t in client.get("/me").json()["targets"]}
    assert targets == {"enem": False, "fuvest": True}


def test_remove_target_soft_deletes_and_allows_recreation(client: TestClient) -> None:
    _register(client)
    target_id = client.post("/me/targets", json={"exam": "enem", "year": 2027}).json()["id"]

    assert client.delete(f"/me/targets/{target_id}").status_code == 204
    assert client.get("/me").json()["targets"] == []
    # the partial unique lets the same exam+year come back after the soft delete
    assert client.post("/me/targets", json={"exam": "enem", "year": 2027}).status_code == 201


def test_remove_unknown_target_not_found(client: TestClient) -> None:
    _register(client)

    response = client.delete("/me/targets/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_me_lists_user_and_targets(client: TestClient) -> None:
    _register(client)
    client.post("/me/targets", json={"exam": "enem", "year": 2027})

    body = client.get("/me").json()
    assert body["user"]["email"] == "aluno@example.com"
    assert len(body["targets"]) == 1
