import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from argumenta import __version__
from argumenta.adapters.observability import metrics as obs_metrics
from argumenta.adapters.observability.logging import configure_logging
from argumenta.adapters.observability.telemetry import configure_telemetry
from argumenta.domain import errors
from argumenta.presentation.fastapi.auth import router as auth_router
from argumenta.presentation.fastapi.body_limit import LimitRequestBody
from argumenta.presentation.fastapi.health import router as health_router
from argumenta.presentation.fastapi.me import router as me_router
from argumenta.presentation.fastapi.progress import router as progress_router
from argumenta.presentation.fastapi.reactions import router as reactions_router
from argumenta.presentation.fastapi.request_id import RequestIdMiddleware
from argumenta.presentation.fastapi.submissions import polling_router
from argumenta.presentation.fastapi.submissions import router as submissions_router
from argumenta.presentation.fastapi.telemetry import router as telemetry_router
from argumenta.presentation.fastapi.track import router as track_router
from argumenta.settings import get_settings

_logger = logging.getLogger(__name__)

ERROR_STATUS: dict[type[errors.DomainError], int] = {
    errors.EmailAlreadyRegisteredError: 409,
    errors.AccountNotFoundError: 404,
    errors.InvalidCredentialsError: 401,
    errors.TermsNotAcceptedError: 422,
    errors.GoogleSignInFailedError: 502,
    errors.ExamTargetAlreadyExistsError: 409,
    errors.ExamTargetNotFoundError: 404,
    errors.TooManyAttemptsError: 429,
    errors.ChapterNotFoundError: 404,
    errors.ChapterLockedError: 403,
    errors.ChapterNotWritableError: 409,
    errors.WordCountOutOfRangeError: 422,
    errors.DailyLimitReachedError: 429,
    errors.LlmBudgetExceededError: 503,
    errors.EvaluationFailedError: 502,
    errors.SubmissionNotFoundError: 404,
    errors.TelemetryBatchTooLargeError: 413,
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Argumenta API", version=__version__)
    app.add_middleware(LimitRequestBody, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestIdMiddleware)
    FastAPIInstrumentor.instrument_app(app)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(track_router)
    app.include_router(progress_router)
    app.include_router(submissions_router)
    app.include_router(polling_router)
    app.include_router(reactions_router)
    app.include_router(telemetry_router)

    @app.exception_handler(errors.DomainError)
    async def handle_domain_error(request: Request, exc: errors.DomainError) -> JSONResponse:
        status_code = ERROR_STATUS.get(type(exc), 400)
        if status_code >= 500:
            # the response hides the message from the student on purpose; the
            # log is the only place the real cause survives
            _logger.error("%s: %s", type(exc).__name__, exc)
            obs_metrics.evaluation_failures.add(1, {"error_type": type(exc).__name__})
        return JSONResponse(status_code=status_code, content={"detail": type(exc).__name__})

    return app


# Global process state (root logger handlers, the OTel SDK registry): configured
# once here, at import time, never inside create_app() itself, which tests call
# on every fixture and would otherwise fight pytest's own caplog handler.
configure_logging()
configure_telemetry(get_settings())

app = create_app()
