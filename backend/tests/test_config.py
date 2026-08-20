"""Tests for application configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import DEFAULT_JWT_SECRET, Environment, Settings


def test_cors_origins_accepts_comma_separated_string() -> None:
    settings = Settings(cors_origins="http://a.test, http://b.test")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_cors_origins_accepts_list() -> None:
    settings = Settings(cors_origins=["http://a.test"])
    assert settings.cors_origins == ["http://a.test"]


def test_log_level_is_normalised() -> None:
    assert Settings(log_level="debug").log_level == "DEBUG"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="chatty")


def test_sync_database_url_strips_async_driver() -> None:
    settings = Settings(database_url="postgresql+asyncpg://u:p@host:5432/db")
    assert settings.sync_database_url.startswith("postgresql://")
    assert "+asyncpg" not in settings.sync_database_url


def test_is_production_flag() -> None:
    assert Settings(environment=Environment.PRODUCTION, jwt_secret="x" * 64).is_production is True
    assert Settings(environment=Environment.DEVELOPMENT).is_production is False


def test_production_rejects_the_placeholder_jwt_secret() -> None:
    """Starting production with the committed default secret must fail loudly.

    `_env_file=None` isolates the test from the developer's own `.env`, which
    would otherwise supply a real secret and make this assertion vacuous.
    """
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment=Environment.PRODUCTION, _env_file=None)  # type: ignore[call-arg]


def test_production_rejects_a_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(environment=Environment.PRODUCTION, jwt_secret="too-short")


def test_production_accepts_a_strong_jwt_secret() -> None:
    settings = Settings(environment=Environment.PRODUCTION, jwt_secret="x" * 64)
    assert settings.is_production is True


def test_development_tolerates_the_default_secret() -> None:
    """Developers must not need to generate a secret just to run the app."""
    settings = Settings(environment=Environment.DEVELOPMENT, _env_file=None)  # type: ignore[call-arg]
    assert settings.jwt_secret == DEFAULT_JWT_SECRET
    assert settings.is_production is False


def test_settings_load_from_a_dotenv_file(tmp_path: Path) -> None:
    """Settings must parse a real `.env`, not just keyword arguments.

    Regression test. `cors_origins` is a list, and pydantic-settings JSON-decodes
    complex types straight from the dotenv source — before any `mode="before"`
    validator runs. A plain comma-separated value therefore raised a
    SettingsError, but only when a `.env` file actually existed, so every test
    that passed values directly missed it.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ENVIRONMENT=development           # inline comments are stripped\n"
        "LOG_LEVEL=warning\n"
        "CORS_ORIGINS=http://a.test,http://b.test\n"
        "JWT_SECRET=a-locally-generated-secret\n"
        "DATABASE_URL=postgresql+asyncpg://u:p@localhost:5432/db\n"
    )

    settings = Settings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.log_level == "WARNING"
    assert settings.environment is Environment.DEVELOPMENT
    assert settings.jwt_secret == "a-locally-generated-secret"


def test_dotenv_accepts_a_single_cors_origin(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CORS_ORIGINS=http://only.test\n")

    assert Settings(_env_file=env_file).cors_origins == ["http://only.test"]  # type: ignore[call-arg]


def test_dotenv_tolerates_an_empty_cors_origins(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CORS_ORIGINS=\n")

    assert Settings(_env_file=env_file).cors_origins == []  # type: ignore[call-arg]
