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
    settings = Settings(environment="production", api_bearer_token="a-real-secret", _env_file=None)
    assert settings.environment == "production"


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins=" https://a.example, https://b.example ", _env_file=None)
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
