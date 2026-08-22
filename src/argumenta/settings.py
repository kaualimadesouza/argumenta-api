from pydantic_settings import BaseSettings, SettingsConfigDict

from argumenta.adapters.llm.effort import Effort


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

    # evaluation engine (issue #7): Claude with structured output, temp 0
    anthropic_api_key: str = ""
    evaluation_model: str = "claude-sonnet-5"
    # thinking effort of the graded correction; "high" is the API default, and
    # changing it moves every score, so the calibration workflow watches this file
    evaluation_effort: Effort = "high"
    # character reaction (issue #10): free text, own knob so the flavour beat can
    # move to a cheaper model without touching the graded correction
    reaction_model: str = "claude-sonnet-5"
    reaction_effort: Effort = "low"
    # monthly LLM cap in tokens over evaluations + character_reactions; 0 disables
    llm_monthly_token_budget: int = 10_000_000
    llm_budget_alert_ratio: float = 0.8

    # basic login rate limit, per client IP + e-mail
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300


def get_settings() -> Settings:
    return Settings()
