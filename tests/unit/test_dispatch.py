"""Unit tests of the async hand-off (issue #68): the Lambda dispatcher and the
entrypoint that routes the self-invoke event to the worker."""

import json
import uuid
from typing import Any, cast

from sqlalchemy.orm import Session

from argumenta.adapters.dispatch import EVALUATION_TASK, LambdaEvaluationDispatcher
from argumenta.entrypoints import lambda_handler


class FakeSession:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    def commit(self) -> None:
        self._log.append("commit")


class FakeLambdaClient:
    def __init__(self, log: list[str]) -> None:
        self._log = log
        self.calls: list[tuple[str, str, bytes]] = []

    def invoke(self, *, FunctionName: str, InvocationType: str, Payload: bytes) -> object:  # noqa: N803
        self._log.append("invoke")
        self.calls.append((FunctionName, InvocationType, Payload))
        return {}


class TestLambdaEvaluationDispatcher:
    def test_commits_before_the_self_invoke(self) -> None:
        """The worker execution must find the pending row: dispatching an
        uncommitted submission would evaluate nothing."""
        log: list[str] = []
        client = FakeLambdaClient(log)
        dispatcher = LambdaEvaluationDispatcher(
            cast(Session, FakeSession(log)), "argumenta-api-prod", client
        )

        dispatcher.dispatch(uuid.uuid4())

        assert log == ["commit", "invoke"]

    def test_fires_an_async_event_with_the_task_payload(self) -> None:
        log: list[str] = []
        client = FakeLambdaClient(log)
        dispatcher = LambdaEvaluationDispatcher(
            cast(Session, FakeSession(log)), "argumenta-api-prod", client
        )
        submission_id = uuid.uuid4()

        dispatcher.dispatch(submission_id)

        function_name, invocation_type, payload = client.calls[0]
        assert function_name == "argumenta-api-prod"
        assert invocation_type == "Event"
        assert json.loads(payload) == {
            "task": EVALUATION_TASK,
            "submission_id": str(submission_id),
        }


class TestLambdaHandlerRouting:
    def test_task_event_goes_to_the_worker(self, monkeypatch: Any) -> None:
        seen: list[uuid.UUID] = []
        monkeypatch.setattr(lambda_handler, "evaluate_submission", seen.append)
        submission_id = uuid.uuid4()

        out = lambda_handler.handler(
            {"task": EVALUATION_TASK, "submission_id": str(submission_id)}, None
        )

        assert seen == [submission_id]
        assert out == {"handled": EVALUATION_TASK}

    def test_anything_else_goes_to_the_http_app(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(lambda_handler, "_http", lambda event, context: {"http": True})

        assert lambda_handler.handler({"version": "2.0", "routeKey": "ANY /x"}, None) == {
            "http": True
        }
