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
    assert Settings(environment=Environment.PRODUCTION).is_production is True
    assert Settings(environment=Environment.DEVELOPMENT).is_production is False
