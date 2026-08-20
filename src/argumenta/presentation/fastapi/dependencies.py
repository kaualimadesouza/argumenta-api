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
from argumenta.adapters.db.session import get_session_factory
from argumenta.adapters.google.oauth import HttpGoogleIdentityGateway
from argumenta.adapters.security.argon2_hasher import Argon2PasswordHasher
from argumenta.adapters.security.jwt_tokens import JwtTokenService
from argumenta.adapters.security.rate_limiter import SlidingWindowRateLimiter
from argumenta.application.accounts.ports import GoogleIdentityGateway, RateLimiter
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
