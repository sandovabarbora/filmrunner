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

    # Supabase project URL (https://<ref>.supabase.co); its JWKS verifies user sign-in tokens.
    supabase_url: str | None = None

    # Service-role key for Supabase Storage uploads (crew photos, FR-18). Unset until
    # INBOX #4 (create the `avatars` bucket) is done by the founder; the upload endpoint
    # refuses with 503 until both this and supabase_url are set.
    supabase_service_role_key: str | None = None
    avatar_bucket: str = "avatars"

    # Where browsers can reach this API (used to build absolute URLs such as photo links).
    public_base_url: str = "http://localhost:8000"

    # Comma-separated list of allowed browser origins, or "*" for local dev.
    # Production sets it to the deployed frontend origin.
    cors_origins: str = "*"

    # Web Push (FR-16, ADR-007). Unset in development and until the founder
    # runs backend/scripts/generate_vapid_keys.py and sets these as Fly
    # secrets (INBOX #5) — the feature stays inert (no "Enable notifications"
    # control shown) rather than erroring when they are absent.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    # RFC 8292 requires a contact URI the push services may use to reach the
    # site operator; a generic mailto keeps a real person's address out of
    # this config, but the founder may set her own.
    vapid_subject: str = "mailto:admin@filmrunner.app"

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
