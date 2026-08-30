"""Issue #51: one request id per request, trusted from the caller or minted,
carried on the response and in the logging contextvar for the whole request."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from argumenta.adapters.observability.logging import request_id_var
from argumenta.presentation.fastapi.request_id import RequestIdMiddleware

app = FastAPI()
app.add_middleware(RequestIdMiddleware)


@app.get("/whoami")
def whoami() -> dict[str, str | None]:
    return {"request_id": request_id_var.get()}


client = TestClient(app)


class TestRequestIdMiddleware:
    def test_a_request_id_is_generated_when_the_caller_sends_none(self) -> None:
        response = client.get("/whoami")

        assert response.headers["x-request-id"]
        assert response.json()["request_id"] == response.headers["x-request-id"]

    def test_two_requests_get_different_ids(self) -> None:
        first = client.get("/whoami").headers["x-request-id"]
        second = client.get("/whoami").headers["x-request-id"]

        assert first != second

    def test_a_caller_supplied_id_is_trusted_and_echoed(self) -> None:
        response = client.get("/whoami", headers={"X-Request-Id": "caller-picked-42"})

        assert response.headers["x-request-id"] == "caller-picked-42"
        assert response.json()["request_id"] == "caller-picked-42"

    def test_the_contextvar_does_not_leak_after_the_request_ends(self) -> None:
        client.get("/whoami")

        assert request_id_var.get() is None
