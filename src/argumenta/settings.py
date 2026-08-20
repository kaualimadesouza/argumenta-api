from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUMENTA_", env_file=".env", extra="ignore")

    app_name: str = "argumenta-api"
    database_url: str = "postgresql+psycopg://argumenta:argumenta@localhost:5432/argumenta"


def get_settings() -> Settings:
    return Settings()
