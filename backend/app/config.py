"""Centralized application configuration.

References:
    - pydantic-settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # auth system. Real SSO/SAML is explicitly out of scope — see DESIGN.md.
    api_bearer_token: str = "dev-only-token-change-me"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance.

    Reference: https://docs.python.org/3/library/functools.html#functools.lru_cache
    """
    return Settings()
