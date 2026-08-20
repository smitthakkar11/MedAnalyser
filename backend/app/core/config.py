"""Application configuration.

All configuration is environment-driven (12-factor). Nothing in the codebase may
read `os.environ` directly — everything goes through the `Settings` object
returned by :func:`get_settings`, so that configuration is typed, validated once
at startup, and trivially overridable in tests.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Placeholder secret shipped in `.env.example`; rejected in production.
DEFAULT_JWT_SECRET = "change-me-in-production-use-a-long-random-value"

#: Minimum HMAC key length for HS256 (RFC 7518 section 3.2).
MINIMUM_JWT_SECRET_BYTES = 32

# Repository root: backend/app/core/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Environment(StrEnum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Typed application settings, loaded from environment variables / `.env`."""

    model_config = SettingsConfigDict(
        # A local backend/.env wins over the repo-root .env, which is shared with
        # docker compose and the frontend.
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application --------------------------------------------------------
    app_name: str = "MedAnalyser"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    api_prefix: str = "/api"

    # --- Database -----------------------------------------------------------
    database_url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+asyncpg://medanalyser:medanalyser@localhost:5432/medanalyser"
        ),
        description="SQLAlchemy async database URL (asyncpg driver).",
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # --- Security -----------------------------------------------------------
    #: Must be replaced with a long random value before production. HS256 keys
    #: shorter than 32 bytes weaken the signature (RFC 7518 §3.2).
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    google_client_id: str = ""
    google_client_secret: str = ""

    # --- CORS ---------------------------------------------------------------
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # --- LLM ----------------------------------------------------------------
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    model_name: str = "llama3.1:8b-instruct-q4_K_M"
    llm_timeout_seconds: int = 120

    # --- Embeddings ---------------------------------------------------------
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    # --- Storage ------------------------------------------------------------
    storage_provider: str = "local"
    file_storage_path: Path = Path("./storage")
    max_upload_size_mb: int = 20

    # --- Doctor discovery ---------------------------------------------------
    doctor_provider: str = "mock"
    maps_api_key: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """Accept a comma-separated string as well as a real list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @model_validator(mode="after")
    def _require_a_strong_production_secret(self) -> Settings:
        """Refuse to start in production with a weak or placeholder JWT secret.

        Failing at startup is far better than silently signing tokens with a
        value that is public in the repository.
        """
        if self.environment is Environment.PRODUCTION:
            if self.jwt_secret == DEFAULT_JWT_SECRET:
                raise ValueError("JWT_SECRET must be changed from its default value in production.")
            if len(self.jwt_secret.encode()) < MINIMUM_JWT_SECRET_BYTES:
                raise ValueError(
                    f"JWT_SECRET must be at least {MINIMUM_JWT_SECRET_BYTES} bytes in production."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def sync_database_url(self) -> str:
        """Same database, using a synchronous driver.

        Some tooling (notably Alembic's offline mode and psql-style utilities)
        does not speak asyncpg.
        """
        return str(self.database_url).replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()
