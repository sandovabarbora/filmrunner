"""Centralized application configuration.

References:
    - pydantic-settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SERVICE_TOKEN_LENGTH = 32
DEV_BEARER_TOKEN = "dev-only-token-change-me"


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or .env.

    Note: no secrets have defaults other than the local-dev database, so a
    misconfigured production deployment fails fast instead of silently
    running against a dev database.
    """

    # hide_input_in_errors: a refused boot's message goes to the platform's logs, and the input is every secret.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FILMRUNNER_", hide_input_in_errors=True)

    database_url: str = "postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner"
    # Fail closed: forgetting this on a deploy must not switch the token checks below off.
    # Local work, CI and docker-compose set it to "development" explicitly.
    environment: str = "production"
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
    # FR-57: extracting contacts from an old call sheet PDF. Without the key the
    # heuristics pass runs alone; with it, Claude does the structured extraction.
    # FR-51 / ADR-008: requests per minute on /api/v1/public/* per client IP, and per personal token
    # on the token routes. 0 disables a limit. Sized for a crew on one Wi-Fi: see app/ratelimit.py.
    sandbox_enabled: bool = True
    public_rate_limit_per_ip: int = 300
    public_rate_limit_per_token: int = 30
    # FR-128: the contact-photo endpoint is a cacheable, non-probing GET (no token, no write), so it
    # gets its own per-IP budget rather than sharing the functional one above — see app/ratelimit.py.
    public_rate_limit_per_ip_photos: int = 3000
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    # FR-106: overridable so E2E tests can point geocoding at a local stub
    # server instead of the real Nominatim endpoint (this sandbox's own
    # egress proxy blocks it, same as every other vendor domain).
    nominatim_url: str = "https://nominatim.openstreetmap.org/search"

    # FR-109: the commit this build was deployed from, baked in at `docker build`
    # time via `--build-arg FILMRUNNER_GIT_SHA=$(git rev-parse HEAD)` (see the
    # deploy command in ADR-002). Unset for a local dev server or an image built
    # without the arg; /healthz omits the field entirely rather than reporting a
    # placeholder, so a stale check can tell "unknown" apart from "matches main".
    git_sha: str | None = None

    @model_validator(mode="after")
    def _refuse_weak_token_outside_development(self) -> "Settings":
        if self.environment == "development":
            return self
        if self.api_bearer_token == DEV_BEARER_TOKEN:
            raise ValueError(
                "FILMRUNNER_API_BEARER_TOKEN must be set to a real value when "
                f"FILMRUNNER_ENVIRONMENT is '{self.environment}' (for local work, set FILMRUNNER_ENVIRONMENT=development)"
            )
        # The sandbox signing key is derived from this token and anyone can get a sandbox token to test guesses against offline.
        if len(self.api_bearer_token) < MIN_SERVICE_TOKEN_LENGTH:
            raise ValueError(
                f"FILMRUNNER_API_BEARER_TOKEN must be at least {MIN_SERVICE_TOKEN_LENGTH} characters when "
                f"FILMRUNNER_ENVIRONMENT is '{self.environment}' (for local work, set FILMRUNNER_ENVIRONMENT=development)"
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
