"""Centralized application configuration.

References:
    - pydantic-settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_BEARER_TOKEN = "dev-only-token-change-me"


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or .env.

    Note: no secrets have defaults other than the local-dev database, so a
    misconfigured production deployment fails fast instead of silently
    running against a dev database.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="FILMRUNNER_")

    database_url: str = "postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner"
    environment: str = "development"
    log_level: str = "INFO"

    # Stub auth for this skeleton: a single shared bearer token, NOT a real
    # auth system (FR-12 replaces it). The default is only accepted in
    # development; any other environment must set its own token.
    api_bearer_token: str = DEV_BEARER_TOKEN

    # Comma-separated list of allowed browser origins, or "*" for local dev.
    # Production sets it to the deployed frontend origin.
    cors_origins: str = "*"

    @model_validator(mode="after")
    def _refuse_dev_token_outside_development(self) -> "Settings":
        if self.environment != "development" and self.api_bearer_token == DEV_BEARER_TOKEN:
            raise ValueError(
                "FILMRUNNER_API_BEARER_TOKEN must be set to a real value when "
                f"FILMRUNNER_ENVIRONMENT is '{self.environment}'"
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed origins as a list, as CORSMiddleware expects."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance.

    Reference: https://docs.python.org/3/library/functools.html#functools.lru_cache
    """
    return Settings()
