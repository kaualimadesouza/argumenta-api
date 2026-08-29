from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response

from argumenta.adapters.security.jwt_tokens import JwtTokenService, TokenPair
from argumenta.application.accounts.ports import (
    AccountRepository,
    GoogleIdentityGateway,
    PasswordHasher,
)
from argumenta.application.accounts.use_cases import (
    LoginWithEmail,
    LoginWithEmailUseCase,
    LoginWithGoogle,
    LoginWithGoogleUseCase,
    RegisterWithEmail,
    RegisterWithEmailUseCase,
)
from argumenta.application.ports import RateLimiter
from argumenta.domain.accounts import UserAccount
from argumenta.presentation.fastapi.dependencies import (
    AppSettings,
    BearerToken,
    IsMobileClient,
    get_account_repository,
    get_google_gateway,
    get_password_hasher,
    get_rate_limiter,
    get_token_service,
)
from argumenta.presentation.fastapi.schemas import (
    GoogleLoginRequest,
    LoginRequest,
    RefreshResponse,
    RegisterRequest,
    UserResponse,
)
from argumenta.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

Accounts = Annotated[AccountRepository, Depends(get_account_repository)]
Hasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]
Google = Annotated[GoogleIdentityGateway, Depends(get_google_gateway)]
Tokens = Annotated[JwtTokenService, Depends(get_token_service)]


def _set_auth_cookies(response: Response, pair: TokenPair, settings: Settings) -> None:
    response.set_cookie(
        "access_token",
        pair.access_token,
        max_age=settings.access_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    # refresh token only travels to the auth endpoints
    response.set_cookie(
        "refresh_token",
        pair.refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/auth",
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _finish_auth(
    response: Response,
    user: UserAccount,
    tokens: JwtTokenService,
    settings: Settings,
    mobile: bool,
) -> UserResponse:
    """Cookies are set either way, so a web session keeps working even if a
    client wrongly sends the mobile header; only the body changes."""
    pair = tokens.issue_pair(user.id)
    _set_auth_cookies(response, pair, settings)
    body = UserResponse.from_domain(user)
    if mobile:
        body.access_token = pair.access_token
        body.refresh_token = pair.refresh_token
    return body


@router.post("/register", status_code=201)
def register(
    body: RegisterRequest,
    response: Response,
    accounts: Accounts,
    hasher: Hasher,
    tokens: Tokens,
    settings: AppSettings,
    mobile: IsMobileClient,
) -> UserResponse:
    use_case = RegisterWithEmailUseCase(accounts, hasher)
    user = use_case.execute(
        RegisterWithEmail(
            email=body.email,
            nickname=body.nickname,
            password=body.password,
            accepted_terms=body.accepted_terms,
        )
    )
    return _finish_auth(response, user, tokens, settings, mobile)


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    accounts: Accounts,
    hasher: Hasher,
    limiter: Limiter,
    tokens: Tokens,
    settings: AppSettings,
    mobile: IsMobileClient,
) -> UserResponse:
    use_case = LoginWithEmailUseCase(accounts, hasher, limiter)
    user = use_case.execute(
        LoginWithEmail(email=body.email, password=body.password, client_key=_client_key(request))
    )
    return _finish_auth(response, user, tokens, settings, mobile)


@router.post("/google")
def login_google(
    body: GoogleLoginRequest,
    response: Response,
    accounts: Accounts,
    google: Google,
    tokens: Tokens,
    settings: AppSettings,
    mobile: IsMobileClient,
) -> UserResponse:
    use_case = LoginWithGoogleUseCase(accounts, google)
    user = use_case.execute(LoginWithGoogle(code=body.code, redirect_uri=body.redirect_uri))
    return _finish_auth(response, user, tokens, settings, mobile)


@router.post("/refresh")
def refresh(
    response: Response,
    tokens: Tokens,
    accounts: Accounts,
    settings: AppSettings,
    bearer: BearerToken,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> RefreshResponse | None:
    """A web session's refresh token lives only in its httpOnly cookie, so a
    204 with no body is all it needs; a mobile client has no cookie to renew,
    so it hands its refresh token back via `Authorization` and gets a new pair
    in the body instead."""
    token = refresh_token or bearer
    if token is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    user_id = tokens.verify(token, kind="refresh")
    if user_id is None or not accounts.is_active(user_id):
        raise HTTPException(status_code=401, detail="invalid or expired refresh token")
    pair = tokens.issue_pair(user_id)
    _set_auth_cookies(response, pair, settings)
    if refresh_token is not None:
        response.status_code = 204
        return None
    return RefreshResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/auth")
