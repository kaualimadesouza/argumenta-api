from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from argumenta import __version__
from argumenta.presentation.fastapi.dependencies import DbSession

router = APIRouter()

UNAVAILABLE = 503


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    database: str


@router.get("/health")
def health() -> HealthResponse:
    """Liveness, and dependency-free on purpose: it must answer while the database
    is down, or a probe cannot tell a dead process from an unusable one."""
    return HealthResponse(status="ok", version=__version__)


@router.get(
    "/health/ready",
    responses={UNAVAILABLE: {"description": "a dependency is not answering"}},
)
def ready(session: DbSession, response: Response) -> ReadyResponse:
    """Readiness: 503 while the database is unreachable, so a deploy or a monitor
    finds out instead of the student."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # the failed statement aborted the transaction; without the rollback the
        # request teardown commits, raises, and the honest 503 becomes a 500
        session.rollback()
        response.status_code = UNAVAILABLE
        return ReadyResponse(status="unavailable", database="down")
    return ReadyResponse(status="ok", database="up")
