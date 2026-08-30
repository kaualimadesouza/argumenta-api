"""AWS Lambda entrypoint: one function, two event shapes. The API Gateway
proxy event goes to the FastAPI app via Mangum; the self-invoke task payload
(adapters.dispatch) goes to the evaluation worker."""

from typing import Any

from mangum import Mangum

from argumenta.adapters.dispatch import EVALUATION_TASK, EvaluationTaskPayload
from argumenta.entrypoints.evaluation_worker import evaluate_submission
from argumenta.entrypoints.rest_application import app

_http = Mangum(app)


def handler(event: dict[str, Any], context: Any) -> Any:
    if event.get("task") == EVALUATION_TASK:
        payload = EvaluationTaskPayload.model_validate(event)
        evaluate_submission(payload.submission_id)
        return {"handled": EVALUATION_TASK}
    return _http(event, context)
