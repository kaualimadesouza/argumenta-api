"""Dispatchers implementing the EvaluationDispatcher port (issue #68).

Inline runs the correction in the caller's request and transaction (local dev
and tests). The Lambda one commits the pending row and asynchronously invokes
this same function with a task payload, which entrypoints.lambda_handler
routes to the evaluation worker."""

import uuid
from typing import Literal, Protocol

import boto3
from pydantic import BaseModel
from sqlalchemy.orm import Session

from argumenta.application.gameplay.use_cases import EvaluateSubmissionUseCase

EVALUATION_TASK = "evaluate_submission"


class EvaluationTaskPayload(BaseModel):
    """The self-invoke event; anything else the Lambda receives is HTTP."""

    task: str = EVALUATION_TASK
    submission_id: uuid.UUID


class LambdaInvoker(Protocol):
    """The one boto3 call we make, as a structural type so tests need no AWS."""

    def invoke(
        self,
        *,
        FunctionName: str,  # noqa: N803
        InvocationType: Literal["Event"],  # noqa: N803
        Payload: bytes,  # noqa: N803
    ) -> object: ...


class InlineEvaluationDispatcher:
    """No queue locally: evaluate now, in the same request and transaction."""

    def __init__(self, evaluate: EvaluateSubmissionUseCase) -> None:
        self._evaluate = evaluate

    def dispatch(self, submission_id: uuid.UUID) -> None:
        self._evaluate.execute(submission_id)


class LambdaEvaluationDispatcher:
    """Fire-and-forget self-invoke: the commit first makes the pending row
    visible to the worker execution (a lost race would surface as a retried
    SubmissionNotFoundError, not a lost correction)."""

    def __init__(
        self, session: Session, function_name: str, client: LambdaInvoker | None = None
    ) -> None:
        self._session = session
        self._function_name = function_name
        self._client: LambdaInvoker = client if client is not None else boto3.client("lambda")

    def dispatch(self, submission_id: uuid.UUID) -> None:
        self._session.commit()
        payload = EvaluationTaskPayload(submission_id=submission_id)
        self._client.invoke(
            FunctionName=self._function_name,
            InvocationType="Event",
            Payload=payload.model_dump_json().encode(),
        )
