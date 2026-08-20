import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from argumenta.adapters.db.repositories.accounts import (
    SqlAlchemyAccountRepository,
    SqlAlchemyExamTargetRepository,
)
from argumenta.adapters.db.repositories.gameplay import (
    SqlAlchemyDailyActivityWriter,
    SqlAlchemyDraftRepository,
    SqlAlchemyEvaluationContextRepository,
    SqlAlchemyProgressWriter,
    SqlAlchemySubmissionRepository,
)
from argumenta.adapters.db.repositories.llm_budget import SqlLlmBudget
from argumenta.adapters.db.repositories.track import (
    SqlAlchemyActivityRepository,
    SqlAlchemyContentRepository,
    SqlAlchemyProgressRepository,
)
from argumenta.adapters.db.session import get_session_factory
from argumenta.adapters.google.oauth import HttpGoogleIdentityGateway
from argumenta.adapters.llm.claude_engine import ClaudeEvaluationEngine
from argumenta.adapters.security.argon2_hasher import Argon2PasswordHasher
from argumenta.adapters.security.jwt_tokens import JwtTokenService
from argumenta.adapters.security.rate_limiter import SlidingWindowRateLimiter
from argumenta.adapters.spelling.spylls_checker import SpyllsSpellChecker
from argumenta.application.accounts.ports import GoogleIdentityGateway, RateLimiter
from argumenta.application.evaluation.ports import EvaluationEngine
from argumenta.application.evaluation.use_cases import EvaluateArgumentUseCase
from argumenta.application.gameplay.use_cases import SubmitArgumentUseCase
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
def _rate_limiter_singleton() -> SlidingWindowRateLimiter:
    settings = get_settings()
    return SlidingWindowRateLimiter(
        max_attempts=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter_singleton()


def get_google_gateway() -> GoogleIdentityGateway:
    settings = get_settings()
    return HttpGoogleIdentityGateway(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def get_current_user_id(
    token_service: Annotated[JwtTokenService, Depends(get_token_service)],
    access_token: Annotated[str | None, Cookie()] = None,
) -> uuid.UUID:
    if access_token is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    user_id = token_service.verify(access_token, kind="access")
    if user_id is None:
        raise HTTPException(status_code=401, detail="invalid or expired token")
    return user_id


CurrentUserId = Annotated[uuid.UUID, Depends(get_current_user_id)]


def get_content_repository(session: DbSession) -> SqlAlchemyContentRepository:
    return SqlAlchemyContentRepository(session)


def get_progress_repository(session: DbSession) -> SqlAlchemyProgressRepository:
    return SqlAlchemyProgressRepository(session)


def get_activity_repository(session: DbSession) -> SqlAlchemyActivityRepository:
    return SqlAlchemyActivityRepository(session)


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


def get_evaluation_engine() -> EvaluationEngine:
    settings = get_settings()
    return ClaudeEvaluationEngine(
        api_key=settings.anthropic_api_key, model=settings.evaluation_model
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


def get_submit_argument_use_case(
    contexts: Annotated[
        SqlAlchemyEvaluationContextRepository, Depends(get_evaluation_context_repository)
    ],
    submissions: Annotated[SqlAlchemySubmissionRepository, Depends(get_submission_repository)],
    progress: Annotated[SqlAlchemyProgressWriter, Depends(get_progress_writer)],
    activity: Annotated[SqlAlchemyDailyActivityWriter, Depends(get_daily_activity_writer)],
    drafts: Annotated[SqlAlchemyDraftRepository, Depends(get_draft_repository)],
    evaluate: Annotated[EvaluateArgumentUseCase, Depends(get_evaluate_argument_use_case)],
) -> SubmitArgumentUseCase:
    return SubmitArgumentUseCase(contexts, submissions, progress, activity, drafts, evaluate)
