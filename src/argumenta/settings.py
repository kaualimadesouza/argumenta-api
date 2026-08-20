from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUMENTA_", env_file=".env", extra="ignore")

    app_name: str = "argumenta-api"
    database_url: str = "postgresql+psycopg://argumenta:argumenta@localhost:5432/argumenta"

    # auth: HS256 JWT in httpOnly cookies; the default secret only exists so dev
    # and tests boot; prod MUST set ARGUMENTA_JWT_SECRET
    jwt_secret: str = "dev-only-secret-change-me-before-production"  # nosec B105  # pragma: allowlist secret
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14
    cookie_secure: bool = False

    # Google OAuth (authorization code flow); created by hand in Cloud Console
    google_client_id: str = ""
    google_client_secret: str = ""

    # basic login rate limit, per client IP + e-mail
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300


def get_settings() -> Settings:
    return Settings()
