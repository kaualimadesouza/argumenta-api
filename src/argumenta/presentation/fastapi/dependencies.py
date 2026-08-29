import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from argumenta.adapters.db.repositories.accounts import (
    SqlAlchemyAccountRepository,
    SqlAlchemyExamTargetRepository,
    SqlAlchemyPushDeviceRepository,
)
from argumenta.adapters.db.repositories.gameplay import (
    SqlAlchemyDailyActivityWriter,
    SqlAlchemyDraftRepository,
    SqlAlchemyEvaluationContextRepository,
    SqlAlchemyProgressWriter,
    SqlAlchemySubmissionRepository,
)
from argumenta.adapters.db.repositories.llm_budget import SqlLlmBudget
from argumenta.adapters.db.repositories.progress import SqlAlchemyStatsRepository
from argumenta.adapters.db.repositories.reactions import SqlAlchemyReactionRepository
from argumenta.adapters.db.repositories.telemetry import SqlAlchemyTelemetryRepository
from argumenta.adapters.db.repositories.track import (
    SqlAlchemyActivityRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyProgressRepository,
)
from argumenta.adapters.db.session import get_session_factory
from argumenta.adapters.google.oauth import HttpGoogleIdentityGateway
from argumenta.adapters.llm.evaluation_engine import LlmEvaluationEngine
from argumenta.adapters.llm.factory import build_provider
from argumenta.adapters.llm.reaction_engine import LlmReactionEngine
from argumenta.adapters.security.argon2_hasher import Argon2PasswordHasher
from argumenta.adapters.security.jwt_tokens import JwtTokenService
from argumenta.adapters.security.rate_limiter import SlidingWindowRateLimiter
from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.application.accounts.ports import GoogleIdentityGateway
from argumenta.application.evaluation.ports import EvaluationEngine
from argumenta.application.evaluation.use_cases import EvaluateArgumentUseCase
from argumenta.application.gameplay.use_cases import SubmitArgumentUseCase
from argumenta.application.ports import RateLimiter
from argumenta.application.reactions.ports import ReactionEngine
from argumenta.application.reactions.use_cases import GetCharacterReactionUseCase
from argumenta.application.telemetry.use_cases import RecordTelemetryEventsUseCase
from argumenta.settings import Settings, get_settings


def get_db() -> Iterator[Session]:
    """One transaction per request: commit on success, rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_account_repository(session: DbSession) -> SqlAlchemyAccountRepository:
    return SqlAlchemyAccountRepository(session)


def get_exam_target_repository(session: DbSession) -> SqlAlchemyExamTargetRepository:
    return SqlAlchemyExamTargetRepository(session)


def get_push_device_repository(session: DbSession) -> SqlAlchemyPushDeviceRepository:
    return SqlAlchemyPushDeviceRepository(session)


def get_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


@lru_cache
def _token_service_singleton() -> JwtTokenService:
    settings = get_settings()
    return JwtTokenService(
        secret=settings.jwt_secret,
        access_ttl_seconds=settings.access_token_ttl_seconds,
        refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
    )


def get_token_service() -> JwtTokenService:
    return _token_service_singleton()


@lru_cache
def _limiter(name: str, max_attempts: int, window_seconds: int) -> SlidingWindowRateLimiter:
    """One sliding window per process and per name: in memory is enough for a
    single container beta, and with N workers the effective limit is N times
    this one (the limiter says so itself)."""
    return SlidingWindowRateLimiter(max_attempts=max_attempts, window_seconds=window_seconds)


def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return _limiter(
        "login", settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds
    )


def get_google_gateway() -> GoogleIdentityGateway:
    settings = get_settings()
    return HttpGoogleIdentityGateway(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """A mobile client has no cookie jar to trust (React Native's own docs call
    cookie auth unstable), so it sends the token itself instead."""
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ")


BearerToken = Annotated[str | None, Depends(bearer_token)]


def is_mobile_client(x_argumenta_client: Annotated[str | None, Header()] = None) -> bool:
    return x_argumenta_client == "mobile"


IsMobileClient = Annotated[bool, Depends(is_mobile_client)]


def get_current_user_id(
    token_service: Annotated[JwtTokenService, Depends(get_token_service)],
    accounts: Annotated[SqlAlchemyAccountRepository, Depends(get_account_repository)],
    bearer: BearerToken,
    access_token: Annotated[str | None, Cookie()] = None,
) -> uuid.UUID:
    """The account lookup is what ends a session: the token is stateless, so
    after `DELETE /me` only the database knows it is worthless."""
    token = access_token or bearer
    if token is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    user_id = token_service.verify(token, kind="access")
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    if not accounts.is_active(user_id):
        raise HTTPException(status_code=401, detail="this account no longer exists")
    return user_id


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]


def get_content_repository(session: DbSession) -> SqlAlchemyContentRepository:
    return SqlAlchemyContentRepository(session)


def get_progress_repository(session: DbSession) -> SqlAlchemyProgressRepository:
    return SqlAlchemyProgressRepository(session)


def get_activity_repository(session: DbSession) -> SqlAlchemyActivityRepository:
    return SqlAlchemyActivityRepository(session)


def get_stats_repository(session: DbSession) -> SqlAlchemyStatsRepository:
    return SqlAlchemyStatsRepository(session)


def get_evaluation_context_repository(
    session: DbSession,
) -> SqlAlchemyEvaluationContextRepository:
    return SqlAlchemyEvaluationContextRepository(session)


def get_submission_repository(session: DbSession) -> SqlAlchemySubmissionRepository:
    return SqlAlchemySubmissionRepository(session)


def get_progress_writer(session: DbSession) -> SqlAlchemyProgressWriter:
    return SqlAlchemyProgressWriter(session)


def get_daily_activity_writer(session: DbSession) -> SqlAlchemyDailyActivityWriter:
    return SqlAlchemyDailyActivityWriter(session)


def get_draft_repository(session: DbSession) -> SqlAlchemyDraftRepository:
    return SqlAlchemyDraftRepository(session)


@lru_cache
def get_evaluation_engine() -> EvaluationEngine:
    """One HTTP client for the process: an Anthropic client per request means a
    connection pool per request."""
    settings = get_settings()
    return LlmEvaluationEngine(
        build_provider(
            settings,
            vendor=settings.llm_vendor,
            model=settings.evaluation_model,
            timeout=settings.evaluation_timeout_seconds,
        ),
        effort=settings.evaluation_effort,
    )


def get_spell_checker() -> SpyllsSpellChecker:
    return SpyllsSpellChecker()


def get_llm_budget(session: DbSession) -> SqlLlmBudget:
    settings = get_settings()
    return SqlLlmBudget(
        session,
        monthly_token_budget=settings.llm_monthly_token_budget,
        alert_ratio=settings.llm_budget_alert_ratio,
    )


def get_evaluate_argument_use_case(
    engine: Annotated[EvaluationEngine, Depends(get_evaluation_engine)],
    spell_checker: Annotated[SpyllsSpellChecker, Depends(get_spell_checker)],
    budget: Annotated[SqlLlmBudget, Depends(get_llm_budget)],
) -> EvaluateArgumentUseCase:
    return EvaluateArgumentUseCase(engine, spell_checker, budget)


def get_reaction_repository(session: DbSession) -> SqlAlchemyReactionRepository:
    return SqlAlchemyReactionRepository(session)


@lru_cache
def get_reaction_engine() -> ReactionEngine:
    settings = get_settings()
    return LlmReactionEngine(
        build_provider(
            settings,
            vendor=settings.reaction_llm_vendor or settings.llm_vendor,
            model=settings.reaction_model,
            timeout=settings.reaction_timeout_seconds,
        ),
        effort=settings.reaction_effort,
    )


def get_character_reaction_use_case(
    reactions: Annotated[SqlAlchemyReactionRepository, Depends(get_reaction_repository)],
    content: Annotated[SqlAlchemyContentRepository, Depends(get_content_repository)],
    engine: Annotated[ReactionEngine, Depends(get_reaction_engine)],
    budget: Annotated[SqlLlmBudget, Depends(get_llm_budget)],
) -> GetCharacterReactionUseCase:
    return GetCharacterReactionUseCase(reactions, content, engine, budget)


def get_submit_argument_use_case(
    contexts: Annotated[
        SqlAlchemyEvaluationContextRepository, Depends(get_evaluation_context_repository)
    ],
    submissions: Annotated[SqlAlchemySubmissionRepository, Depends(get_submission_repository)],
    progress: Annotated[SqlAlchemyProgressWriter, Depends(get_progress_writer)],
    activity: Annotated[SqlAlchemyDailyActivityWriter, Depends(get_daily_activity_writer)],
    drafts: Annotated[SqlAlchemyDraftRepository, Depends(get_draft_repository)],
    evaluate: Annotated[EvaluateArgumentUseCase, Depends(get_evaluate_argument_use_case)],
    exams: Annotated[SqlAlchemyExamTargetRepository, Depends(get_exam_target_repository)],
) -> SubmitArgumentUseCase:
    return SubmitArgumentUseCase(contexts, submissions, progress, activity, drafts, evaluate, exams)


def get_telemetry_repository(session: DbSession) -> SqlAlchemyTelemetryRepository:
    return SqlAlchemyTelemetryRepository(session)


def get_telemetry_rate_limiter() -> RateLimiter:
    settings = get_settings()
    return _limiter(
        "telemetry",
        settings.telemetry_rate_limit_batches,
        settings.telemetry_rate_limit_window_seconds,
    )


def get_record_telemetry_use_case(
    events: Annotated[SqlAlchemyTelemetryRepository, Depends(get_telemetry_repository)],
    limiter: Annotated[RateLimiter, Depends(get_telemetry_rate_limiter)],
) -> RecordTelemetryEventsUseCase:
    return RecordTelemetryEventsUseCase(events, limiter)
