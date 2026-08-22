from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from argumenta import __version__
from argumenta.domain import errors
from argumenta.presentation.fastapi.auth import router as auth_router
from argumenta.presentation.fastapi.health import router as health_router
from argumenta.presentation.fastapi.me import router as me_router
from argumenta.presentation.fastapi.reactions import router as reactions_router
from argumenta.presentation.fastapi.submissions import router as submissions_router
from argumenta.presentation.fastapi.telemetry import router as telemetry_router
from argumenta.presentation.fastapi.track import router as track_router
from argumenta.settings import get_settings

_ERROR_STATUS: dict[type[errors.DomainError], int] = {
    errors.EmailAlreadyRegisteredError: 409,
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
    errors.TelemetryTimestampError: 422,
}


def create_app() -> FastAPI:
    app = FastAPI(title="Argumenta API", version=__version__)
    max_bytes = get_settings().max_request_bytes

    @app.middleware("http")
    async def refuse_oversized_bodies(request: Request, call_next: Any) -> Response:
        """Refused on the header, before anything is deserialized: parsing a
        60 MB batch just to answer 413 costs hundreds of megabytes of RSS, and
        the worker that dies takes the corrections down with it."""
        if _declared_length(request) > max_bytes:
            return JSONResponse(status_code=413, content={"detail": "RequestTooLarge"})
        response: Response = await call_next(request)
        return response

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(track_router)
    app.include_router(submissions_router)
    app.include_router(reactions_router)
    app.include_router(telemetry_router)

    @app.exception_handler(errors.DomainError)
    async def handle_domain_error(request: Request, exc: errors.DomainError) -> JSONResponse:
        status_code = _ERROR_STATUS.get(type(exc), 400)
        return JSONResponse(status_code=status_code, content={"detail": type(exc).__name__})

    return app


def _declared_length(request: Request) -> int:
    """A body with no Content-Length (chunked) reads as zero here and is bounded
    instead by the transport cap on the request model."""
    declared = request.headers.get("content-length")
    if declared is None or not declared.isdigit():
        return 0
    return int(declared)


app = create_app()
