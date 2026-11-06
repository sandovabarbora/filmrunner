"""Settings guardrails: the dev bearer token must never reach a non-dev environment."""

import pytest

from app.config import DEV_BEARER_TOKEN, Settings


def test_dev_token_is_accepted_in_development() -> None:
    settings = Settings(environment="development", api_bearer_token=DEV_BEARER_TOKEN, _env_file=None)
    assert settings.api_bearer_token == DEV_BEARER_TOKEN


def test_dev_token_is_refused_in_production() -> None:
    with pytest.raises(ValueError, match="FILMRUNNER_API_BEARER_TOKEN must be set"):
        Settings(environment="production", api_bearer_token=DEV_BEARER_TOKEN, _env_file=None)


def test_real_token_is_accepted_in_production() -> None:
    settings = Settings(environment="production", api_bearer_token="x" * 32, _env_file=None)
    assert settings.environment == "production"


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins=" https://a.example, https://b.example ", _env_file=None)
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


def test_environment_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FILMRUNNER_ENVIRONMENT", raising=False)
    assert Settings(api_bearer_token="x" * 32, _env_file=None).environment == "production"


def test_forgetting_the_environment_cannot_boot_on_the_dev_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FILMRUNNER_ENVIRONMENT", raising=False)
    monkeypatch.delenv("FILMRUNNER_API_BEARER_TOKEN", raising=False)
    with pytest.raises(ValueError, match="FILMRUNNER_API_BEARER_TOKEN must be set"):
        Settings(_env_file=None)


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_a_short_token_is_refused_outside_development(environment: str) -> None:
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(environment=environment, api_bearer_token="x" * 31, _env_file=None)


def test_a_32_character_token_is_accepted_in_production() -> None:
    assert Settings(environment="production", api_bearer_token="x" * 32, _env_file=None).api_bearer_token == "x" * 32


def test_a_short_token_is_fine_in_development() -> None:
    assert Settings(environment="development", api_bearer_token="short", _env_file=None).api_bearer_token == "short"


def test_a_refused_boot_does_not_write_secrets_to_the_log() -> None:
    """Failure case: the boot error lands in the platform's logs, so it must not echo what it refused."""
    canary_token = "canary" + "tokenvalue"
    canary_db = "canary" + "dbvalue"
    with pytest.raises(ValueError) as refused:
        Settings(environment="production", api_bearer_token=canary_token, database_url=f"postgresql://u:{canary_db}" + "@h/d", _env_file=None)
    assert canary_token not in str(refused.value)
    assert canary_db not in str(refused.value)
