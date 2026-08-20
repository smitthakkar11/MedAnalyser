"""Tests for application configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings


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
    """Starting production with the committed default secret must fail loudly."""
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(environment=Environment.PRODUCTION)


def test_production_rejects_a_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 bytes"):
        Settings(environment=Environment.PRODUCTION, jwt_secret="too-short")


def test_production_accepts_a_strong_jwt_secret() -> None:
    settings = Settings(environment=Environment.PRODUCTION, jwt_secret="x" * 64)
    assert settings.is_production is True


def test_development_tolerates_the_default_secret() -> None:
    """Developers must not need to generate a secret just to run the app."""
    assert Settings(environment=Environment.DEVELOPMENT).jwt_secret
